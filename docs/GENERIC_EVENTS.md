# Generic event contracts

This is the technical reference for the **current shared event mechanisms**.
[Status](STATUS.md) owns supported/unsupported behavior and current live-test gaps;
[caller evidence](EVENT_COVERAGE.md) links dated results. No section here is a test
queue or a new release claim. Historical versioned contracts keep their original
semantics; extensions below apply only to the named versions/contexts.

- [Ownership and option pages](#ownership-and-option-pages)
- [Card selectors and deck effects](#card-selectors-and-deck-effects)
- [Event rewards and offers](#event-rewards-and-offers)
- [Event combat](#event-combat)
- [Terminal combat rewards](#terminal-combat-rewards)
- [Custom screens and endings](#custom-screens-and-endings)

## Ownership and option pages

<a id="implemented-architecture"></a>

### Parent and child ownership

Handle shared interactions using the rules the game supplies. A new event using
a supported interaction does not need an event-name registration. Event names
identify ownership and representative/held-out cases; custom surfaces may need
separate adapters.

The parent reserves the chosen option and pre-action deck. At the first owned
selector request it may bind appended cards as described below. Owned request
and screen-creation hooks supply operation, counts, candidate originals and task
identity. The child advertises legal actions; a replaceable host provider chooses
one. The adapter rechecks identity before native input, verifies preview/effect
completion, then resumes the parent through Proceed.

G7 and inherited child contracts describe exact two-stage admission semantics;
a parent action may already have effects before an unsupported child appears.
Preserve cumulative child completion independently of the latest parent's effect label.

The summary's `effects` describes the latest parent action, not all effects of
the event. Reconciled card/item children set `card_effect_verified` or
`item_effect_verified`; the next parent dispatch, including Proceed, resets it
to `unverified`. A resolved flow with `effects: unverified` and
`completed_card_children: 1` therefore retains one verified card child. Parent
`map_handoff` reconciliation establishes event exit, not verification of arbitrary
parent effects or a fresh core map decision. The shared client's `event-map`
flow separately checks that core decision and preserves the original event summary
on success or failure. See the [bridge guide](../bridge/Sts2AgentBridge/README.md).

<a id="implemented-repeated-ordinary-option-pages"></a>

### Repeated ordinary option pages

The parent can revisit option keys and accept identical keys/text on consecutive
pages. Pinned `AbyssalBaths.Linger` allocates new options, and the ordinary
`NEventRoom.SetOptions` path clears and rebuilds the native option controls.
Those control identities establish a new presentation; text or flag changes alone
do not. The owned `Chosen` task must succeed and child/overlay work must settle
before an ordinary transition reconciles. All controls on a dispatched page,
including unchosen ones, are retired for the session. A page retaining any retired
control waits within the existing pending-read bound and cannot receive input.

Each reconciled choice advances the decision identity. The shared host reserves
that decision rather than the localization key, while retaining receipt/history
checks and replay rejection. Read/apply identity and legality revalidation, danger
masking, 12 parent actions, 52 total actions and all existing read/time bounds
remain. This is an expansion of admitted native behavior with the same wire
shape and decision/action semantics; repeated pages require the updated bundled
host. An `option_transition` verifies callback/page progress, not arbitrary HP or
gold effects. No uncertain action is retried.

<a id="implemented-ancient-dialogue-and-optional-selections"></a>

### Ancient dialogue and optional selections

The shared parent admits the pinned `NAncientEventLayout` alongside ordinary
`NEventLayout`. While native dialogue remains, it exposes one `choose:0` action
with text “Continue dialogue”. This emits the owned dialogue hitbox's native
Released signal once. Completion requires exactly one line advancement on the
same layout, event, hitbox and dialogue list with unchanged line identities.
Hidden or disabled input waits; replaced objects, changed lines, jumps, exceptions
and exhausted waits stop the session. There is no fabricated Chosen task for a
dialogue action. Dialogue uses the existing parent action budget (12).

The last native dialogue line enables ordinary event options. Those options use
the existing Chosen/child ownership and effect checks. Dialogue that restarts
after a completed relic pickup is handled before Proceed. Proceed still requires
the native callback and actionable map. No event-name admission list is added.
Automatic relic effects without a child remain unverified parent effects.

Two explicit child versions extend the existing card envelope:

| Contract | Native selection | Completion and bounds |
| --- | --- | --- |
| `card_add_v2` | Event `FromSimpleGridForRewards` → `NSimpleCardSelectScreen`; min=0, max=1..15; manual confirmation | Select zero through max, then Confirm; at most 16 child actions. Complete nonempty offer domain of up to 64, including domain equal to max. Exact selected additions and unchanged baseline deck. |
| `card_transform_v3` | Event `FromDeckForTransformation` → `NDeckTransformSelectScreen`; min=0, max=1..8; manual confirmation | Select a subset, explicitly open preview below max, then Confirm. At max the native selector opens preview. Complete nonempty domain of up to 64, including domains smaller than max. Existing 10-action limit. |

The pinned acceptance callers are **Orobas/SeaGlass** (one combined 15-card grid,
0..15) and **Tanx/Claws** (0..6). Zero is a submitted selection, not cancellation.
Both selector and request results must be exactly empty, the overlay must close,
the complete deck must remain unchanged, and Chosen must succeed. Claws still
invokes one native transform command for zero: the journal requires exactly one
successful command returning the native empty array, with no choice, modification,
insertion or removal effects. Missing, repeated, faulted or effect-bearing empty
commands cannot resolve. Preview cancellation is never exposed.

Generic add-card grids use exact allocated native holders and their clickability,
without inferred scroll dimensions or whole-grid viewport fit. Grid/holder/card/
hitbox identity, animation state, Confirm ownership and native task/deck outcome
checks remain enforced. This also permits zero-selection Confirm on a larger grid.

Optional behavior is enabled only by an explicit event context. Existing positive
selection versions, standalone card contracts and their limits remain unchanged.
Host and production boundary validation require the new matching descriptor and
payload versions; confirmed histories and exact selected sets remain mandatory.
This selector contract does not establish every ancient pickup. Nested pickups,
true cancellation and empty candidate domains remain unsupported; item inventory
policies are separate from optional card selection.

## Card selectors and deck effects

<a id="implemented-appended-cards-before-a-selector"></a>

### Appended cards before a selector

The first owned card-selector request can establish a deck baseline that includes
cards appended by the preceding event callback. The original pre-action deck must
remain an exact prefix: identical card objects, order, keys, upgrade levels and
enchantment identities/values. New cards must belong to the same player and run;
the complete deck remains bounded at 512 cards. Binding happens once, before
native selector creation, with the existing parent ownership and empty-overlay
checks. Prepending, replacing, removing, reordering or modifying original cards
is unsupported by this contract.

The request-time deck then stays fixed through admission, target selection and
preview. All shared card families use it, including transform effect observations
and reward-offer exclusion. The existing selected-only child effect checks apply
to that deck. Appended-card ownership remains checked; non-enchantment selectors
also retain those cards' enchantment identities because their older child codecs
omit enchantment fields. Enchantment selectors retain their full-deck checks.
No later deck change can refresh the baseline, and a second request cannot rebind it.

This accepts a pre-selector deck state; it does not verify the source or intended
effect of the automatic additions. `card_effect_verified` still describes only
the verified selector effect. No public fields, action meanings, hooks, retry
behavior or selector limits change. The removal-specific post-selection extension
below is separate; other selectors still reject post-selection additions.

Pinned callers include Grave of the Forgotten/Confront (Decay before SoulsPower),
Trial/MerchantInnocent (Shame before two upgrades), and Trial/NondescriptInnocent
(Doubt before two transformations). The pinned `AddCursesToDeck` path appends to
the deck. Their automatic additions remain outside the selector effect guarantee.

<a id="implemented-removal-followed-by-one-appended-grant"></a>

### Removal followed by one appended grant

Generic removal children advertise **`card_remove_v2`** before input. The
shared card session uses an explicit event-removal policy; standalone
`card_selection_v1` removal keeps its exact baseline-minus-selection guarantee.
Existing selection counts, preview/confirm actions, task ownership, action bounds
and parent completion checks remain. Older generic clients reject the new child
version rather than silently accepting broader semantics.

Removal uses native input on the exact allocated holder, so admission no longer
requires computed whole-grid dimensions, full viewport containment or unchanged
scroll position. It retains the exact grid and allocated holder domain, native
`_isClickable`, hitbox validity/identity/enabled state, visible nodes and settled
selection state. Grid replacement, destruction or animation and target/domain
changes still prevent input. Fixtures cover five- and twenty-card layouts,
mid-selection resizing/scrolling and exact preview/removal/map completion. These
are not live off-screen removal evidence.

The adapter captures the complete actual deck, including enchantment descriptors
and player/run ownership. Selecting and previewing require the unchanged request
baseline. After confirmation, only selected originals may disappear; all survivors
must retain identity, order, key, upgrade and enchantment identity/value. Once all
selected originals are absent, the selector is closed and its exact task result
matches the committed set, at most **one** new card may follow those survivors.
The grant cannot reuse any baseline card, candidate, or nonbaseline observed clone.
A legitimate baseline card produced by an earlier transformation remains eligible.

The first observed appended identity, key, level and enchantment are retained
through pending reads. Disappearance, replacement, reordering or descriptor
changes reject; no baseline refresh hides those changes. The child still waits
for both request and chosen-option tasks to complete successfully. A grant does
not excuse a failed callback, extra removal or unfinished selector.

Resolved v2 payloads keep `selected_cards` for the verified removals and separately
include `parent_additions: {status: "unverified", cards: [...]}`. Each observed
card exposes only its key, upgrade level and optional enchantment key/amount.
The list has zero or one entries. These observations do not establish the grant's
provenance or intended identity, and do not add child actions or effect counts.
The parent `card_effect_verified` label still refers to the selected removal.

Pinned callers include Amalgamator/CombineStrikes and CombineDefends: two removals
followed by one appended merged card. The v2 result verifies selected removals,
not the provenance of that grant.
Multiple grants, interleaved/prepended additions, other post-selector operations
and changes to surviving cards remain unsupported.

<a id="implemented-all-eligible-transform-holders"></a>

### Allocated transform holders

All eligible **allocated** holders are exposed in native order with complete
candidate/domain binding. Input uses the shared direct native holder path in
`components/events/native/GenericEventV7TransformAdapter.cs`; it has no fixed-slot
or inferred whole-grid viewport restriction. A card without an allocated holder
cannot use this path.

Exact holder/model/run/screen/task ownership, native clickability, enabled hitbox,
deferred-callback identity, original preview membership and selected-only effects
remain required. Matching card names do not establish identity. Missing, disabled
or reassigned targets stop without choosing a substitute. Fixed/variable preview
semantics remain distinct. The old card16 restriction belonged to a historical
experiment, not the production contract.

<a id="implemented-allocated-upgrade-holders"></a>

### Allocated upgrade holders

Generic fixed-count upgrades (1–8) use their existing direct holder input
without requiring the entire eligible grid to fit inside the viewport. The exact
allocated domain remains bounded at 64 cards; unallocated cards are unsupported.
The adapter retains holder/model/card/hitbox identity, native `_isClickable` and
hitbox enabled state, settled highlights, exact preview originals (or mapped
multi-upgrade clones), task results and selected-only deck effects. Multi-upgrade
input retains its dispatch ticket through the deferred native callback. Scroll
position and viewport size are not target identity.

The pinned `NCardHolder._GuiInput` checks `_isClickable` before deferring
`EmitPressed` on that holder. Input completion must retain that exact identity.
This generic-event extension does not broaden the standalone Smith-one contract.

<a id="implemented-one-card-enchantment"></a>

### Single-card enchantment

The shared `CardSelectCmd.FromDeckForEnchantment` request and
`NDeckEnchantSelectScreen` form a `card_enchant_v1` child of the existing
`generic_event_v10` parent. No event-name admission rule is added. Sapphire Seed's Plant and Nourish branch is a concrete caller. Pinned
metadata also confirms `FieldOfManSizedHoles.EnterYourHole` requests one card,
applies an enchantment and finishes the event.

The initial scope is `min_select = max_select = 1`, `preview_confirm`, and
2–64 eligible allocated candidates. Every offered candidate must be previously
unenchanted; stacking, replacement and cancellation remain unsupported.
This v1 path is single-card; the fixed multi-card extension is described below. The request binds canonical enchantment identity, public key,
positive integer amount, preferences, player/run, exact original cards and tasks.
The native command copies and sorts its input by deck position, so screen admission
checks those exact originals in deck order rather than requiring the same list object.

Selection uses the shared direct holder input. Before confirmation, the adapter
verifies the before-card original and the after-card enchanted preview clone,
including owner, card key, upgrade level, enchantment key and amount. It retains
the preview containers, holders, card nodes, clone and enchantment identities
across reads. Completion requires the exact selected original to gain the requested
enchantment, with unchanged card key, upgrade level, deck order and all unselected
cards/enchantments. The first observed effect identity must remain stable.
The selector/request/parent tasks must complete successfully and the overlay must
close before the child resolves. Uncertain mutations are never retried.

The new child wire version keeps the existing selection actions and candidate
shape. Ready and resolved payloads append
`"enchantment": {"key": "SOWN", "amount": 1}`; waiting/unsupported observations
use `null`. Receipts and failures carry `card_enchant_v1` without that field.
The resolved descriptor reports the exact verified effect on the selected original;
selected-card fields retain its original key/upgrade level. Native object identities
are never serialized. The host binds the descriptor for the whole child and
rejects version, cardinality, key or amount changes. Existing child versions retain
their wire shapes.

<a id="implemented-fixed-multi-card-enchantment"></a>

### Fixed multi-card enchantment

`card_enchant_v2` extends the same owned enchantment request to fixed counts
2–8, with more eligible allocated candidates than the requested count (up to
64). Waterlogged Scriptorium/Prickly Sponge is the representative two-card
Steady caller. Native source confirms that its multi-selection preview contains
the **selected original cards**, while single selection uses an enchanted clone.
The adapter therefore reuses the exact original-preview path used by removal,
with the native enchantment container and confirm control. Reaching the fixed
count opens that preview automatically; there is no separate preview action.

Every selected original must gain the requested key/amount with its own retained
enchantment identity. Effects may arrive across successive reads. An effect that
was already observed cannot disappear or be replaced, and two originals cannot
share one effect object. Deck identity/order, card keys/upgrades, unselected
cards, exact selector/request results, successful parent completion and closed
overlay remain required. Deferred input waits for the exact preview and never
permits an early confirm. Single-card v1 retains its existing preview and wire
semantics; v2 carries the same public fields with fixed multi-card cardinality.

<a id="implemented-generic-deck-transformation-selectors"></a>

### Generic deck transformation selectors

`FromDeckGeneric` with the native transformation prompt admits a fixed-one,
noncancelable `NDeckCardSelectScreen` child. WoodCarvings/Bird and Torus are the
representative pinned callers: they filter transformable deck cards, show this
original-card preview, then call `TransformTo<Peck>` or
`TransformTo<ToricToughness>`. That command forwards through the existing observed
batch transformation path.

Admission uses the native prompt's localization table/key (`card_selection` /
`TO_TRANSFORM`), not event names or rendered English. The prompt classifies intent;
it does not prove the eventual effect. The screen's filtered/sorted original list
is authoritative: 2–64 distinct, owned, transformable baseline cards with exact
allocated holder bindings. The bridge does not rerun filter or sorting callbacks.
Other prompts, optional/multiple selection, cancellation and selectorless automatic
completion remain outside this contract. The existing removal request's nested
`FromDeckGeneric` call retains its outer request ownership.

The child reuses `card_transform_v2`: select one advertised slot, then confirm its
exact original-card preview. The generic screen does not display a generated
replacement preview, so none is fabricated. Before confirmation the adapter checks
current native legality, expected selection, preview/control identity and deck,
then reserves the original before input can complete the selector task. The
existing journal must witness the selected original's removal, exact replacement
and insertion order, successful command result, unchanged survivors, completed
selector/request/Chosen tasks and closed overlay. A prompt, click receipt or deck
change alone cannot report success. Public wire shape and host actions are unchanged.

## Event rewards and offers

<a id="implemented-multiple-potionrelic-rewards"></a>

### Ordered potion/relic rewards

One owned, nonterminal `RewardsSet.Offer` may yield 2–8 populated, unlinked
potion/relic entries. The new generic item child uses `item_set_v1`; a singleton
keeps `item_v1`. Whispering Hollow/Gold (two potions) and War Historian Repy's
Unlock Chest (two potions and two relics) supply representative native shapes.
This is the ordinary item-reward screen, distinct from event card-reward menus.

The child collects entries in their original generated-list order. Each entry
retains its exact reward/model identity, native type index and control. Public
`collect:N` indexes are zero-based **list positions** within the set: the game's
`RewardsSetIndex` identifies a type and can repeat for two potions or two relics.
Duplicate offered model identities, linked rewards, unsupported reward types,
foreign controls and changed list membership/order are rejected. Before the first
collection, an ordered capacity plan requires each potion to fit in an initially
free slot or a slot supplied by a preceding pinned Potion Belt. A later belt cannot rescue an earlier full-inventory potion **under this ordered
contract**. Screens/policies requiring skip, discard or reordered capacity
collection use the separate `item_policy_v1` contract below.

Each entry uses the existing `item_v1` observation/action/effect checks. Its
collection task must succeed before advancing. Completed entries retain their
selected flag, exact claim, collection task and potion slot across subsequent
entries. Original potion slots remain fixed apart from verified insertions; the
known capacity pickup below may append empty slots. The last collection also waits for the original Offer and
Chosen tasks and automatic closure of the owned reward screen. Native rewards
stay in the list after collection; removed/freed completed buttons are allowed.
Relic substitution, nested pickup selectors and other inventory-changing pickup
effects remain unsupported by the existing exact-effect boundary.

The versioned read envelope contains, in order, `version`, `session_nonce`,
`status`, `offer_count`, `collected` and `current`. `collected` is an immutable
prefix of resolved `item_v1` payloads. `current` is the next single-entry
`item_v1` observation, or null while awaiting final completion or after a stop.
Action receipts retain their `item_v1` shape under the `item_set_v1` child
descriptor. A resolved set has all entries in `collected` and null `current`.
The host checks the ordered receipts, stable history and next entry before input;
older consumers reject the new descriptor rather than interpreting it as v1.

One set counts as one child episode and one completed item child. Each reconciled
collection contributes separately to child action counts. A later failure retains
earlier reconciled collections without claiming set or parent completion, and a
lost mutation reply never causes a retry. The existing event-wide action/read
budgets still apply; the set has a shared 256-read local bound.

<a id="implemented-offline-event-potion-belt-capacity-pickup"></a>

### Event Potion Belt capacity pickup

Owned singleton, ordered item-set and mixed card/item rewards support the
pinned `PotionBelt` pickup, including item rewards opened by the owned Resume
callback. The shared native recognizer requires the exact native type, stable
`POTION_BELT` key and `PotionSlots` value two. Its native `AfterObtained` → `GainMaxPotionCount` path appends empty slots.

Admission simulates the original reward order using initially free slots and
preceding known +2 grants, bounded to eight slots. Each belt must initially be
unowned. Collection must finish with the exact relic owned once by the player,
exactly two appended empty slots and unchanged original potion identities. Pending
collection may expose the original or expected enlarged capacity; another entry
cannot start until collection and its exact effect reconcile. Later entries use
fresh potion-slot baselines, and every settled belt, capacity gain and collected
potion remains checked through set completion. Resume-time rewards retain the
final inventory and ownership through the continuation handoff.

The existing `item_v1`, `item_set_v1` and `mixed_reward_set_v1` wire contracts stay
unchanged. The next entry's ordinary `potion_slots` includes newly available slots;
relic results still certify the claimed model, with capacity verified by the native
completion adapter. These ordered contracts do not themselves acquire skip,
discard or priority actions. `item_policy_v1` separately handles screens requiring
those policies. Other capacity effects and nested pickup selectors remain unsupported.

<a id="implemented-ordinary-event-card-reward-menus"></a>

### Single ordinary card reward

`card_reward_v1` adds a `card_reward` child for one populated, unlinked, exact
`CardReward` in an owned nonterminal `RewardsSet.Offer`. The representative pinned
caller is **BrainLeech/Rip** (canonical RewardCount one); **TheFutureOfPotions/Trade**
also offers one reward and upgrades its generated cards before opening the screen.
The Cheese add-card grid remains a separate interaction.

The child first advertises `open` on the exact native reward button. Observational
hooks retain the resulting `NCardRewardSelectionScreen`, its original generated
`CardCreationResult` list and the actual task returned by `OptionSelected()`.
That returned async task is distinct from the screen's retained completion source.
Once native holders are clickable, `choose:N` selects one of 1–5 original offers;
slots are zero-based menu positions, even when keys repeat. Input uses the exact
allocated holder and the existing native Pressed signal mechanism.

The ordinary default Skip alternative is supported only when native reward/set
legality and its enabled, visible control permit it. Alternative type, identifier,
post-selection behavior and default callback identity are retained. **Skip only
closes the card menu**: it leaves the root reward uncollected. The child then
advertises `dismiss` on the exact enabled root Proceed button, which finishes the
owned reward set. An interrupted menu returning null is not a successful Skip.

Choosing verifies the exact task-result slot, removal of only that offer from the
generated list, and insertion of the original offered card into the deck. The
insertion position is retained once observed; baseline cards keep identity,
relative order, key, level, enchantment and player/run ownership. A sole chosen
offer legitimately leaves `IsPopulated` false. Skip/dismiss verifies no deck change
and no successful collection. Both paths require the original collection, Offer
and Chosen tasks to succeed and all owned overlays to close before parent resume.
The reward baseline is the actual deck at generated-screen binding; preceding
automatic parent effects are not independently verified by this child.

The child descriptor contains `ordinal`, `parent_decision_id`, `parent_action_id`,
`kind: card_reward`, `contract_version: card_reward_v1` and `offer_count: 1`.
Read fields, in order, are `version`, `session_nonce`, `status`, `phase`,
`decision_id`, `cards`, `can_skip`, `legal_actions`, `prior_results` and
`selected_slot`. Ready `choose` cards expose `slot`, `key` and `upgrade_level`;
other phases have an empty list. Receipts contain `version`, `session_nonce`,
`decision_id`, `action_id` and `outcome`. Ordered history records `opened` then
`collected`, or `opened`, `skipped`, `dismissed`. Only final resolution exposes
the selected slot (null for Skip). One menu counts as one card child, including
a verified Skip/dismiss; it uses at most three actions and 256 reads. The wire and
host validate lineage, versions, stable offers, receipts and history. Lost replies
stop without retry. Older consumers reject the new child descriptor.

The multiple-entry extension is described below.
Mixed card/item sets use the versioned extension below. Repeated offers within one option, SpecialCardReward, reroll/multiple picks,
hook-substituted cards and nested pickup selectors remain unsupported.

<a id="implemented-multiple-card-reward-menus"></a>

### Multiple card reward menus

`card_reward_set_v1` extends the same `card_reward` child family to **2–8 ordinary
CardReward entries in one owned nonterminal RewardsSet**. The pinned representative
is **ColorfulPhilosophers/OfferRewards**: three rewards, normally three cards per
menu, followed by event completion. Every reward has native `RewardsSetIndex=5`;
public indexes therefore use retained generated-list positions and exact reward
identities.

The child visits each reward once, in list order. `open:N` opens that reward's
menu; `choose:N:S` selects original slot S and `skip:N` uses the ordinary native
Skip alternative when legal. Each menu still has 1–5 offers. A verified choice
removes only its original offer and inserts that exact card; a verified Skip
closes the menu without changing the deck. Skipped reward buttons stay on the
root screen and cannot be reopened through this child. If any reward was skipped,
`dismiss` is advertised **after every menu is settled**, on the exact native root
Proceed control. Collecting every reward instead uses native automatic closure.

The admission deck snapshot remains fixed through entry zero. Before each later
entry starts, the previous active entry's complete deck and result must remain
valid. The later snapshot includes those verified insertions; this does not admit
new unrelated additions, removals, reordering or upgrades between menus. All
reward/list identities, offered models and metadata, prior selection flags,
collection/choice task identities and results remain retained. Future entries
cannot collect early. Duplicate rewards/models, linked or
empty rewards, replaced controls and changed prior effects stop the flow.
The starting deck plus one possible card per reward must fit the 512-card bound. Root Offer and Chosen task failures always
stop it, including after earlier menus have succeeded.

Read payloads retain the card-reward fields and append `offer_count`, `offer_index`
and `settled`. `offer_index` is the next generated-list position, or the count when
all menus are settled. Each ordered settled row has `offer_index`, `selected_slot`,
`key`, `upgrade_level` and `result` (`collected` or `skipped`); a skipped row has
null card fields. The top-level `selected_slot` remains null for sets. Current
cards and legal actions describe only the active menu. Receipts carry the new set
version and namespaced action. History records each open and choice/Skip, then the
single final dismissal if needed. Singleton `card_reward_v1` wire shape and
completion semantics remain unchanged; internal entry completion is never
published as singleton completion.

Each settled menu contributes two reconciled actions; one set counts as one card
child only after all native tasks succeed and the root closes. A later failure
retains earlier verified rows/counts without claiming completion. The set uses at
most 17 actions and 256 reads, within the existing event-wide budgets. Wire and
host validate stable settled prefixes, exact card values, menu-specific receipts,
legal transitions and final dismissal. Lost mutation replies stop without retry.
Reentry into the outer session blocks subsequent inner input and cleanup retains
ownership on failure.

Mixed card/item sets use the versioned extension below. Repeated
Offers within one option, SpecialCardReward, rerolls/multiple picks, substituted
cards and nested pickup selectors remain separate gaps.

<a id="implemented-mixed-carditem-reward-sets"></a>

### Mixed card/item reward sets

`mixed_reward_set_v1` extends the existing set session to **2–8 ordinary card,
potion and relic rewards in one owned nonterminal RewardsSet**, with at least one
card and one item. The pinned concrete caller is **LostCoffer.AfterObtained**:
its generated list contains a three-card CardReward followed by a PotionReward,
passed to `RewardsCmd.OfferCustom`. Lost Coffer is offered by Neow. Callback construction order can differ from the
admitted screen order; the bridge follows the actual retained screen list.

Entries retain the admitted native reward-list order; callers must use exposed
`offer_kinds` rather than infer order from callback construction. Cards use
`open:N`, `choose:N:S` and legal
`skip:N`; items use `collect:N` through the existing item adapter and exact native
collection task. Each item settles after its collection succeeds and its exact
model/claim effect is verified. Offer and Chosen completion belong to the whole
set. If any card was skipped, the exact root Proceed control provides one final
`dismiss`, including when the last entry is an item. Otherwise native automatic
closure applies. This ordered contract has no item Skip or replacement actions;
its capacity plan must fit every potion using preceding known belt gains. The
separate `item_policy_v1` contract handles policies that need those extra actions.

The admission deck remains fixed through leading items. Only verified card
insertions advance its baseline. Initial potion slots plus verified insertions and
known capacity gains, settled item claims, assigned slots and collection task identities remain valid
across later menus and collections. An item pickup that changes the deck, an
unexpected inventory change during a card menu, a cleared prior claim, changed
slot/task, early future entry or failed parent task stops the episode. Nested
pickup selectors and hook-substituted cards remain unsupported.

The six-field descriptor keeps `kind: card_reward`, sets the new contract version
and includes `offer_count`. Set reads append `offer_kinds` (ordered `card`, `potion`
or `relic` values) and `item`; each `settled` row appends `kind`. A ready item uses
`phase: collect`, empty `cards`, `can_skip: false`, its ordinary ready `item_v1`
observation in `item`, and the same decision/`collect:N` action at the top level.
All other phases have `item: null`. An item settlement has null `selected_slot`
and `upgrade_level`, its exact stable key, and `result: collected`. Card rows and
open/choice/Skip history keep their existing meanings. Pure-card and pure-item
versions retain their wire shapes and semantics.

History reconciles **two actions per card, one per item**, plus the final dismissal
when needed. One complete mixed set increments `completed_card_children` once;
it does not also increment `completed_item_children`. Typed settlements expose
its contents. Stable prefixes and the variable action count are checked by both
wire service and host; an uncertain or lost action reply stops without retry.
The existing 256-read/set and event-wide budgets remain in force.

<a id="full-inventory-reward-policies-and-native-terminal-progression"></a>

### Full-inventory item policies

`item_policy_v1` owns an event reward screen when its items cannot all be collected
in the original order. It exposes stable indexed offers, explicit card menus,
public potion-slot keys, legal actions and correlated history. Actions are
`collect:N`, `discard:N`, `choose:N`, `skip_card` and `skip_remaining`. Card collection
opens the native menu; choosing or skipping it is a separate action. Native Proceed
dismisses unclaimed rewards only when that screen permits skipping. Collection,
original-potion discard and final dismissal retain their exact native tasks;
settled claimed models, card effects and unrelated inventory remain bound until
parent completion. New potions cannot be discarded by this policy. The maximum is
25 child actions across at most eight offers and eight original potion slots.

The event host’s `--event-potion-policy` supports `skip-full` (default), `skip-all`,
`replace-first` and `stop-on-full`. Capacity grants are preferred before replacement.
The same policy applies to owned resume-time item screens. Existing fitting item
sets retain their earlier contracts. The pinned source has no concrete resume-time
card/selector caller; this implementation makes no broader resume claim.

#### Nested pickup boundary

Source inspection used pinned `sts2.dll` SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Bounded inspection found that ordinary relic reward rolls select rarities
2/3/4, while identified pickup selector relics use shop/ancient rarities 5/7.
Small Capsule and Toy Box therefore do not establish the proposed ordinary random
reward → nested-selector case. Shop pickup selectors use their own scoped adapter; this does not admit nested
selectors within event/resume reward children.

<a id="implemented-choose-one-cards-and-bundles"></a>

### Required card offers and bundles

Two native selection surfaces compose with the same event parent, including
ancient dialogue/options and Proceed/map. **Neow/ScrollBoxes** is the pinned bundle
caller. LeadPaperweight and MassiveScroll use the direct-card surface but pass
`canSkip=true`, so their actual admission uses **card_offer_v2** below. No required
v1 caller was found in the bounded retained-caller inspection. Admission uses the
owned request/screen chain and native models, without an event or relic allowlist.

| Contract | Native path | Legal flow and bounds |
| --- | --- | --- |
| `card_offer_v1` | `FromChooseACardScreen` → `NChooseACardSelectionScreen` | One `choose:i`; native admission accepts 1–3 offers with one card each. `canSkip` must be false. Input waits until more than 350 ms after the native opening timestamp. |
| `bundle_offer_v1` | `FromChooseABundleScreen` → `NChooseABundleSelectionScreen` | `choose:i` → exact native preview → `confirm`; 1–5 bundles, each containing 1–8 cards. |

The child descriptor has `kind: card_offer`, the matching `contract_version`,
`offer_count`, ordinal and parent decision/action lineage. The shared descriptor
and choose-action grammar have capacity for five offers; native direct-card
admission retains the pinned three-offer limit. Payload fields are `version`,
`session_nonce`, `status`, `phase`, `decision_id`, `offers`, `legal_actions`,
`prior_results` and `selected_index`. Each offer contains its `index` and ordered
`cards` (`slot`, `key`, `upgrade_level`). Ready/resolved payloads retain the exact
initial domain. Waiting/unsupported payloads expose no legal actions or offers.
Bundle history records `previewed`, then `collected`; direct choice records
`collected`. A completed child retains its parent's ownership until Proceed/map.

The adapter retains exact offered models, list order, screen, selector completion
source, controls/hitboxes and bundle preview card nodes. Native clickability,
visibility and enabled state gate input. Bundle preview uses the original moved
card nodes; same-model replacement holders or controls cannot inherit a decision.
Before completion, selector and request results must identify exactly the chosen
model or bundle, the real request and Chosen tasks must succeed, the overlay must
close, and the original deck must be unchanged followed by exactly the selected
cards in order. Baseline and offer ownership are retained. Partial ordered additions
and deferred input/tasks wait; unrelated changes, failures or exhausted waits stop.
The deck limit remains 512. Each input is attempted at most once.

These v1 contracts do not add Skip, preview
cancellation, extra grants/copies, card substitution or nested pickups. Optional
choose-one offers and one extra grant now have the separate v2 contract below.
Native direct menus with more than three choices are rejected.

<a id="implemented-optional-card-offers-and-one-appended-grant"></a>

### Optional card offers and one appended grant

`card_offer_v2` extends the direct ChooseACard family only when the owned native
request has `canSkip=true`. **Neow/HeftyTablet** is the representative caller:
its pinned `AfterObtained.MoveNext` passes true at IL185–186, creates Injury at
IL313, inserts the chosen card at list index zero only when non-null at IL324–340,
and awaits enumerable `CardPileCmd.Add` at IL350. Choosing therefore adds the
selected original followed by Injury; Skip still adds Injury. Admission remains
generic, with no event/relic allowlist. Other optional requests may add no extra.

LeadPaperweight also uses `canSkip=true` with no appended grant.

The descriptor remains `kind: card_offer`, now with `contract_version: card_offer_v2`
and 1–3 offers. The ready phase exposes `choose:0` through the final offered index,
then `skip`. Either action is attempted once. Skip dispatches the exact
`NChoiceSelectionSkipButton` retained through both the screen's `_skipButton`
field and `SkipButton` node path. Its native visibility/enabled state, the offer
controls and owned screen must remain valid. The existing opening delay is retained
for the whole ready surface. Native Skip itself completes the selector with an
empty sequence; completion also requires the actual request to return null,
Chosen to succeed and the overlay to close. Chosen input instead requires both
selector and request results to identify the selected original model.

The baseline deck must retain exact order, identities, metadata, enchantments and
ownership. No addition is allowed before an input attempt. After choosing, the
selected original must be the first appended card; after either choosing or
skipping, zero or one additional card may follow. That extra model must belong to
the same player/run, have valid metadata, and differ from every baseline and
offered model. Once observed, its identity and metadata cannot change or disappear.
Ordered partial additions and deferred input/task completion wait within the
existing read budget. Multiple extras, prepended/interleaved grants, offered-model
reuse, changed survivors, cancellation and nested children stop the session.
Admission reserves room for the selected card plus one extra within the 512-card
limit. Required offers and bundles retain their strict v1 rules.

The payload retains all v1 fields in their original order and appends
`additional_cards`. This list is empty except in a resolved payload, where it has
zero or one `{slot: 0, key, upgrade_level}` entry. It is an observation of the extra
card, **not verified grant provenance or a prediction of the event's cost**. The
resolved history is `collected` with the chosen `selected_index`, or `skipped` with
`selected_index: null`. Both count as one completed card child. All v2 outcomes
leave parent `effects: unverified`; core, wire and host retain that distinction
through reconciliation and map return. Lost input/replies are never retried.

<a id="implemented-inactive-combat-layouts-and-result-acknowledgment"></a>

### Inactive combat layouts and results acknowledgment

The parent admits the pinned `NCombatEventLayout` while `HasCombatStarted`
is false and its native embedded room remains valid and unchanged. Ordinary
options and existing children use the same ownership and completion rules.
**PunchOff/Nab** is the representative interaction: Injury is added before the
singleton relic reward, then Proceed returns to map. **TheLanternKey/ReturnTheKey**
is another source-backed noncombat candidate. Layout admission alone does not
certify combat entry. The separate non-resuming handoff below admits a narrow
combat path; other entries stop as unsupported. Native options do not expose a
reliable pre-choice combat flag, so unsupported entries may stop after the
authorized choice has started combat.

The `card_results_v1` child acknowledges the pinned `NSimpleCardsViewScreen`
opened by an owned event callback. **Darv/PandorasBox** supplies the inspected
caller; Darv's pool eligibility remains unresolved. Pandora's Box performs its
automatic transformation first, then opens a capstone screen with the results.
The hook retains the exact returned screen, results list and added-card models,
current capstone container, native ConfirmButton and post-transformation deck.
The method declares `NCardsViewScreen` as its return type; the hook receives that
base type and requires the exact concrete `NSimpleCardsViewScreen` instance at
runtime. The release verifier compares this declaration and the postfix/fixture
signatures against pinned game PE metadata. This path needs no synthetic selector
task: Confirm closes the native capstone synchronously (deferred input may still wait).
Completion requires that exact capstone to close, Chosen to succeed and the
entire post-show deck to remain unchanged in model/order/key/upgrade/enchantment
and ownership. The result list must contain 1–64 successful, unique models
currently present exactly once in the deck. The existing 512-card deck limit applies.

The descriptor uses `kind: card_results`, `contract_version: card_results_v1`,
parent lineage/ordinal and `offer_count` for the result-card count. Payload fields
are `version`, `session_nonce`, `status`, `phase`, `decision_id`, `cards`,
`legal_actions` and `prior_results`. Cards contain `slot`, `key`, `upgrade_level`.
The ready phase is `acknowledge`, with one legal action, `confirm`. Resolved
payloads retain the original result cards and one `acknowledged` history entry.
Waiting/unsupported payloads expose no cards or actions. Confirmation is attempted
at most once; lost input/replies are never retried. Foreign, replaced or prematurely
closed capstones and changed controls/models/decks stop the session.

Acknowledgment counts as a completed card child, but parent effects remain
**`unverified`**. It does not certify the correctness of the earlier automatic
transformation. Wire and host checks reject a fabricated `card_effect_verified`
claim for that acknowledgment. Card inspection, nested/sequential result screens,
results inside an existing pickup/selector child and alternative result screens
remain unsupported.

## Event combat

<a id="implemented-offline-non-resuming-event-combat"></a>

### Non-resuming combat

The adapter observes the owned, non-generic
`EventModel.EnterCombatWithoutExitingEvent` call. It admits zero to eight supported special-card, potion or relic extra rewards
(at most one special-card entry)
with `shouldResumeParentEventAfterCombat=false`, outside any child selector. No event-name rule is used. Dense Vegetation’s Fight page after Rest is a concrete caller.

The native entry method returns `void` and starts room entry through a discarded
task. Its return and the successful option callback are therefore insufficient.
The bridge waits for a live, in-progress combat and binds the exact run, player,
encounter, logical combat room, parent event ID and `NCombatRoom` node, including
its native `_visuals` room reference. A mismatch stops the session. This observes
combat entry, not victory or automatic parent effects.

Parent protocol `generic_event_v10` includes `complete/combat_handoff` and its matching
history result. The existing `/probe/generic-event-v7/` routes remain stable;
older protocol clients reject the new version. `map_handoff` still requires an
accepted Proceed. The Python summary exposes `destination`, so `event-map` cannot
mistake an entered fight for a returned map.

The unified router disposes the event module before transferring its exact combat
scope to core. Failed cleanup stops the host. Transfer clears the combat reader’s
previous terminal cache and records the witnessed new combat. Until core observes
that same combat’s terminal result, only combat and combat-choice routes (plus
metadata) are admitted. Changed identities stop the host; they are never retried.

`event-combat-map` composes this entry with the existing bounded combat, reward
and map controllers. It preserves separate `event` and `combat_flow` summaries;
the latter retains combat, rewards and map results even when a later stage fails.
Defeat does not start rewards. Reward coverage includes gold, ordinary card choices, direct special-card
grants and exact potion/relic collection; other reward surfaces stop with the preceding evidence intact.

The resuming path below adds a separate callback witness. Resuming entry with
extra rewards and arbitrary embedded combat branches remain unsupported.

<a id="implemented-offline-event-combat-resumption"></a>

### Callback-verified resumption

The same entry observer admits `shouldResumeParentEventAfterCombat=true`
with no event-supplied extra rewards. It binds the original logical `EventRoom`
and the concrete `EventModel.Resume(AbstractRoom): Task` declaration before the
fight can end. The initial event session resolves to `combat_resume_handoff`,
with matching history and a retained session nonce, rather than claiming map
return or victory. Battleworn Dummy is a concrete caller. Automatic upgrades in its callback remain
unverified parent effects and do not exercise a multi-card selector.

The original event module remains the cleanup owner during combat. After the
owned choice task and exact combat entry reconcile, ordinary event hooks are
removed while the exact resume hook and three item observation hooks remain. Ownership is rechecked immediately
before unpatching; interference or cleanup failure stops the bridge. Core combat
and combat-choice routes use the same native legality and action bounds as before.
Other capability routes remain blocked; only the owned resume-item routes below
can service an interactive resume callback.

The read-only `/probe/event-combat-v2/public/decision` route returns schema 1,
protocol `event_combat_v2`, the initial event `session_nonce`, and status
`combat`, `waiting`, `item` or `resumed`. It is available only during an owned resuming
combat. An ending fight or room transition waits for the callback; a late combat
POST is rejected before dispatch as stale. Unknown identities and callback
fault/cancellation stop the host. No uncertain action is retried.

`EventRoom.Resume` is not a completion witness: it starts callbacks without
awaiting them and creates the replacement event node immediately. The bridge
instead requires exactly one callback on the original mutable event, with the
exact exited combat room, and retains the returned Task. Success also requires
the original logical event room, run and player, the new `NEventRoom` matching
that event’s Node, and no active overlay/capstone. A new node alone cannot finish
a pending callback. An unresolved combat chooser blocks release. Successful
module disposal precedes clearing the core combat scope and pending action.

`event-combat-map` handles both destinations. For `combat_resume_handoff`, the
combat host polls the nonce-bound continuation route within its existing
300-second/4096-loop bound, preserving attempted/accepted/reconciled actions.
A successful return is `event_resumed`; training expiry is never labeled victory.
Then one fresh event session runs through Proceed, followed by the existing
five-second actionable-map check. The composite retains `event`, plus
`combat_flow.combat`, `resumed_event` and `map_handoff` even if a later stage fails.
Another combat from that resumed session is not recursively driven by this controller.

`--event-option` selects one exact, currently legal first parent option by its
stable ID, then falls back to the existing first-legal policy. A missing, locked
or ambiguous requested option stops before input; the bridge does not guess a
replacement. For the representative setup use
`--event-option BATTLEWORN_DUMMY.pages.INITIAL.options.SETTING_2` with
`--capability event-combat-map`. This is a reusable host policy, not a native
event allowlist or a strategic policy.

#### Owned item rewards during resumption

A successful **Battleworn Dummy Setting1** callback awaits a generated potion
through `RewardsCmd.OfferCustom`. The bridge observes that callback's exact
`RewardsSet.Offer`, screen creation and collection tasks. Its async scope carries
through delayed generation; a reward screen found outside that scope is not adopted.
Item context uses the retained run/player/logical event room and replacement event
node. The original Chosen task is preserved; the item completion witness is the
actual Resume task.

Continuation status `item` permits GET
`/probe/event-combat-v2/public/item-decision` and POST
`/probe/event-combat-v2/public/item-action`. The POST uses the existing authenticated
decision/action headers, canonical item decision digest and `collect:<index>` action.
The payload reuses `item_v1` for one potion/relic or `item_set_v1` for 2–8 ordered
item entries, including retained collected rows. These are child routes under the
retained event owner, not standalone item sessions. A child result cannot release
combat ownership; only the subsequent verified continuation and successful cleanup
can do so. The earlier continuation v1 route is retired. Current generic parent bodies use
`generic_event_v10` over the existing v7 routes.

Collection requires the exact owned reward/button and an ordered capacity plan:
each potion must fit using initially free slots or a preceding pinned Potion Belt.
The existing item sessions verify the claimed model, exact potion insertion, collection
and Offer tasks, Resume completion and closed screen. Through the final handoff,
the bridge retains successful task identities and settled potion slots/capacity;
changing them stops the host. Faulted/canceled callbacks, duplicate/unowned offers,
foreign overlays, nested pickup selectors and card rewards stop this path.

The combat host services one resume Offer within both its remaining combat budget
and a 30-second/128-read item bound. Each native reward is dispatched at most once.
Its `resume_items` summary preserves attempted/accepted/reconciled counts and
collected public item keys, including partial progress on failure. Every retained
history row is type-validated before another input. Lost or malformed receipts are
never retried.

Setting3 obtains its relic directly through `RelicCmd.Obtain`; it does not
establish a resume-time relic reward screen or selector caller. Passive callback
completion does not certify automatic rewards/upgrades. Full-inventory resume
screens may use [item_policy_v1](#full-inventory-item-policies); the ordered item contracts retain their
own collection order and capacity requirements.

## Terminal combat rewards

These use the shared core reward adapter after combat, not the event-owned
nonterminal reward contracts above. The full screen remains limited to eight entries.

### Extra special-card reward

**The Lantern Key → Keep the Key → Fight** is the concrete caller for this
increment. Pinned static IL shows `TheLanternKey.Fight` creates one
`SpecialCardReward` per player and passes it into the shared combat entry method.
`CombatRoom.AddExtraReward` retains that reward; `RewardsSet.WithRewardsFromRoom`
adds the same object to the room-end reward list. `SpecialCardReward.OnSelect`
adds its specified mutable card directly with `CardPileCmd.Add`; it opens no card
chooser. These are source observations, not live execution.

For the supported single-player entry, the lease captures each unlinked, populated,
uncollected special reward and its card, owner, key and upgrade level. It requires
the exact ordered extra-reward list in the entered combat room and rechecks it
through the combat terminal observation. Resuming combat with extra rewards and
enchanted extra cards remain unsupported.
No event-name registration is used.

The existing public reward routes project `kind: special_card`, one public
card key and the native `take:<slot>` / `claim_special_card` action. Ready payloads
containing a special card use **schema 2**, unless a higher item-session schema
below is required. Ordinary ready payloads, waiting, completion and action receipts retain schema 1. The decision digest includes the
new reward kind and action. Older consumers reject the extension before input.
Both `first-card` and `skip-card` collect the specified special card; those policy
names continue to govern ordinary card-choice menus.

Before input, the core reader retains the exact reward, button and card identities.
One native button click reserves the decision. Reconciliation requires the same
reward screen, successful native selection, exactly one insertion of the specified
card, unchanged health/gold, and the original deck cards in their original order
with unchanged ownership, keys, upgrades and enchantments. A same-key substitute,
extra card, changed survivor, premature map return or foreign screen cannot pass.
Insertion before selection completion waits without another click; lost input
receipts are never retried. The host reports verified grants separately in
`rewards.claimed_special_cards`, preserving them if a later stage fails.

Combat and reward stages establish their own native identities. This does not add
an independent proof of historical event provenance across the handoff, certify
unrelated automatic effects, or establish full-run play.

### Extra potion/relic rewards and mixed collection

**Punch Off → Take Them → Fight** is the concrete caller. Pinned static IL shows
`PunchOff.Fight` supplies an unpopulated `RelicReward` and `PotionReward` to the
non-resuming combat entry. The game populates those entries later. Potion entries
share native reward index 2; relic entries share index 3. These are static source
observations, not a live demonstration of that branch.

The combat lease retains up to eight exact unlinked, uncollected reward objects
with at most one special-card entry
and the original ordered room list. Deferred item generation is allowed until a
model first appears; that model and public key are then retained. The lease rejects
replacement entries, changed indices, duplicate models, wrong players and already
owned relics. Special-card extras retain their populated-card rules above.

The existing core reward reader and controller also collect potion/relic rewards
on ordinary terminal reward screens. A screen containing items uses **ready schema
4**, or schema 5/6 for the specific capacity/healing effects below, for its entire
reward session, including ordinary card children and empty parents after collection. Every reward row appends `item_key`, a bounded public
model key for `potion`/`relic` and null for other kinds. Item rows have empty cards,
null gold and no Skip flag. `collect:0` through `collect:7` use action kind
`collect_item`. Waiting, completion and action receipts remain schema 1.

In schema 3/4, `reward_index` is a session ordinal bound to the original native
reward object; `reward_slot` remains the current visible slot used by actions.
This permits repeated potion/relic entries with identical native indices and keys.
Visible removal or reordering cannot rename an entry or introduce a new reward.
Legacy sessions preserve their native indices and original decision digests.
The complete reward-screen domain is still bounded to eight entries, including
ordinary gold/card rewards; the combat lease’s extra-entry limit does not raise
that screen limit.

Before collection the bridge binds the exact reward, button, player and offered
model. Reconciliation requires native selection and the exact claimed model,
one insertion in a previously empty potion slot or one locally owned relic,
unchanged survivor inventories/deck and unchanged public HP/max-HP/gold/deck count.
A delayed completion waits without another click. Settled items remain checked
until verified reward completion, after which normal later potion use is allowed.
Lost dispatch, mismatched effects, replaced ownership and nested selectors stop
without retry. Full potion inventories withhold collection. The default policy
reports `potion_inventory_full`; explicit skip and replacement policies are described below. The Potion Belt capacity effect below is supported. Other relic pickup effects
that alter these baselines or open a selector remain unsupported.

Both card policies collect items before special/ordinary cards and record only
verified pickups in `rewards.collected_items` as kind, public key and reward index.
Prior verified effects survive later stage failures. Potion Belt capacity and
Fake Lee’s Waffle healing are the explicit effect exceptions below; arbitrary
relic pickup effects may reach the unsupported boundary.

### Terminal Potion Belt capacity pickup

The terminal reward adapter recognizes the pinned native `PotionBelt` model and
its `PotionSlots` value of two. Pinned static IL shows `AfterObtained` calling
`PlayerCmd.GainMaxPotionCount`, which appends empty slots to the player's belt.
A supported pickup preserves every original potion object/key and appends exactly
two null slots, with at most eight total. Collection must also retain the exact
claimed relic and unchanged survivor relics, deck and public player values.
A same-key model of another type does not acquire this permission. Other values,
filled new slots, changed survivors, unexpected growth/shrinkage and pickup selectors
remain unsupported. Oversized growth is withheld before input.

A reward session containing this model uses **ready schema 5** throughout its
parent and card-child decisions. Each reward row appends `potion_capacity_gain`
after `item_key`: two for Potion Belt, zero for other rows. Inventory/actions
retain schema 4's fields. Decision identity uses `reward_v5` and binds the declared
gain. Waiting, completion and receipt payloads stay schema 1; schema 1–4 decoding
remains supported for existing sessions.

When a potion is blocked, the shared reward controller collects an available
capacity-grant relic before stopping for a full inventory or discarding a potion.
The ordinary gold and card policies still apply. After exact gain reconciliation,
it refreshes legal actions and collects potions into the new slots. `skip-all`
continues to leave potion rewards. Verified gains are reported separately in
`rewards.potion_capacity_gains` with key, reward index, and before/after capacity.
A lost receipt never counts the gain; a later pickup failure retains an earlier
verified gain.

Previously collected potions remain bound during growth and afterward. Existing
original inventory potions remain eligible for explicit replacement; newly added
slots and collected potions are excluded from that original-inventory set. A settled
capacity grant must persist until reward completion, including when no potion was
collected before the belt. Custom event and resume-time item rewards use the
[ordered capacity contract](#implemented-offline-event-potion-belt-capacity-pickup)
above. Nested pickup selectors remain unsupported.

### Terminal Fake Lee’s Waffle healing pickup

The terminal adapter recognizes exact native `FakeLeesWaffle`, key
`FAKE_LEES_WAFFLE`, with `Heal.BaseValue` equal to 10. Pinned static IL establishes
healing of `floor(max_hp / 10)`, capped at maximum HP, with no maximum-HP increase.
The reader verifies that exact health result plus unchanged gold, maximum HP,
deck models/upgrades/enchantments, surviving relics and potion slots. A same-key
model of another type or another Heal value cannot grant healing permission.
Other health changes remain unsupported.

A session containing this model uses **ready schema 6** throughout parent and card
child decisions. Every row appends `heal_amount` after schema 5’s
`potion_capacity_gain`: `floor(max_hp / 10)` for this relic, zero for other rows.
The nominal amount remains stable even at full health; reconciliation caps the
actual gain. Decision identity uses `reward_v6` and binds this field. The client
validates the declaration and exact resulting player state. Older ready schemas
and schema 1 waiting/completion/receipt payloads retain their meanings.

The native terminal screen frees a collected reward button and fades its empty
panel while retaining the parent overlay and Proceed. Once the retained reward
reports successful selection, the reader verifies its exact claimed model and
effects without dereferencing the freed button. Before completion, the original
live button remains required. Parent overlay ownership and no-retry rules remain
unchanged. This is a targeted terminal correction; it does not certify other
healing relics, event/resume pickup effects or Merchant reward screens exceeding
the eight-entry projection limit.

### Terminal potion reward policies

The shared client accepts `--potion-policy stop-on-full` (default), `skip-full`,
`skip-all`, or `replace-first` for `rewards`, `combat-map` and the non-resuming path of
`event-combat-map`. The representative case is Punch Off’s terminal potion reward
with a full inventory, alongside gold, cards and its relic reward.

`skip-full` collects each potion while its collection action remains legal. Once
capacity is exhausted, it leaves the remaining potions visible and finishes other
rewards. `skip-all` leaves every uncollected potion even when capacity is available.
Both policies preserve the ordinary first-card/Skip choice policy and relic collection.
They use the native terminal Proceed operation; no potion reward click, discard,
replacement or fabricated skip action is sent for a left-behind potion.

The host keeps uncollected potion identities until Proceed. Disappearance,
replacement, or selection without a corresponding controller action stops the flow.
A stale decision refreshes through the existing bounded path; uncertain mutations
are never retried. Before Proceed, the native adapter captures the exact unclaimed
models, potion slots, survivor relics and deck. It requires unchanged inventory and
unclaimed offers, successful completion of the exact native Proceed task and map
return before completing the reward session. Pinned static IL shows terminal
Proceed runs normal reward skipping; `PotionReward.OnSkipped` records a skipped
choice without collecting or discarding a potion. That observation is not a live test.

The reward summary includes `potion_policy` and `skipped_potions`, each with public
key, stable reward index and reason (`inventory_full` or `policy`). These are
recorded only after verified reward exit. Lost receipts, failed/pending exit tasks,
changed inventory or failed exit reconciliation leave this list empty while
preserving earlier verified collections. A later map-read failure retains the
completed reward summary.

`replace-first` collects rewards that fit, handles the ordinary card choice, then
replaces the first advertised eligible original inventory potion when capacity is
full. It sends `discard:0` through `discard:7` as a separate action, verifies the
removal, then sends the waiting reward's collection action. Only potion objects
present in the same slot at initial reward-session binding are eligible. Newly
collected potions are protected; if no original potion remains eligible, the host
stops with `potion_replacement_unavailable` without leaving the pending offer.
The summary's `discarded_potions` records each verified slot and original public key;
if later collection fails, the verified discard remains recorded independently.

Ready schema 4 extends schema 3 with `potion_slots` (0–8 public keys or nulls) and
`potion_slot` on every legal action (null except for `discard_potion`). Full inventory
plus an unclaimed potion offer is required for any discard action. Ready decisions
bind this inventory under the `reward_v4` identity domain. Schema 1–3 decoding remains
supported; action receipts, waiting and completion remain schema 1. At most 17 legal
actions and 17 accepted mutations fit the existing eight-reward session budget.

Native discard uses the same `DiscardPotionGameAction` and queue as the potion
popup, restricted to the pinned single-player queue. Its `BeforeExecuted` guard
rechecks the exact slot/model/owner, native removal permission, unchanged inventory
and deck, live offer button, screen, queue and out-of-combat state. The guard expires
after five seconds and remains attached if the session fails or is disposed before
execution, preventing a late slot lookup from deleting a replacement object.
Reconciliation requires exact removal, the native removed flag, successful completion
of the same action task and no action exception; unexpected effects or nested screens
stop without retry. Cleanup with an unresolved discard fails explicitly.

These terminal policies are separate from the event/resume `item_policy_v1`
[policies described above](#full-inventory-item-policies). Nested selectors opened by these reward pickups remain
unsupported. See [current status](STATUS.md) for the demonstrated cases.

## Custom screens and endings

<a id="implemented-offline-fake-merchant-custom-screen"></a>

### Fake Merchant

The shared event adapter supports the pinned `NFakeMerchant` inventory flow:
open the initially closed inventory, buy zero to six offered relics, close it,
then use its native Proceed control to reach the map.  It uses existing parent choices, `choose:N` actions and
event/map composition; no additional listener, route or protocol version is needed.

The public choices are `FAKE_MERCHANT.OPEN`,
`FAKE_MERCHANT.BUY.<slot>.<item_key>.<displayed_price>`,
`FAKE_MERCHANT.CLOSE` and `FAKE_MERCHANT.LEAVE`. Buy choices publish the visible
relic key and price and are legal only while the exact native slot is stocked,
visible, enabled and affordable. The default first-legal policy buys affordable
offers in native slot order, then closes and leaves. A choice provider can select
specific advertised offers or close without buying. The complete six-purchase
path consumes nine parent actions.

Entry binds the custom screen, its event, player, logical room, inventory model
and native controls. The six relic slots and entries retain their exact identities,
models, prices and each `MerchantEntry._player` owner. Open and close wait for
native inventory/control transitions. Purchases dispatch once through the slot's
native selection input and wait for that entry's `PurchaseCompleted` callback.
Success requires the exact gold debit, unstocked entry and newly owned relic;
original cards, potions, capacity and retained relic identities/keys remain checked
through map return. New logical option identities are issued only after that
verified effect, allowing the parent to distinguish progress when Godot reuses
inventory nodes. Foreign overlays, combat entry, changed ownership or incompatible
pickup effects stop the flow. An unresolved mutation makes cleanup fail, including
repeated disposal attempts; detaching a callback never certifies cancellation.

The retained target's `FakeMerchant.BeforeEventStarted` creates six relic entries.
`NMerchantSlot` selection invokes the entry purchase, whose completion callback
follows the gold debit, relic acquisition and post-purchase callback. This static
binding inspection used the same pinned game assembly
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
It establishes the intended native path, not live execution evidence.

Already-open entry remains unsupported. The initial Foul Potion combat choice
is described separately below; opening the inventory removes that choice.

#### Initial Foul Potion fight

At Fake Merchant’s untouched initial closed inventory, the first legal owned Foul Potion
adds `FAKE_MERCHANT.FOUL_POTION.<slot>`. It enqueues native potion use once, guards
its exact slot at execution, retains `FoulPotionThrown`, and binds the resulting
combat plus seven exact extra relic rewards. It does not offer this choice after
opening or shopping. Standard combat/reward/map orchestration continues from the
verified handoff; the potion action itself is not victory evidence.

<a id="implemented-offline-crystal-sphere"></a>

### Crystal Sphere

The shared event owner supports both native entry choices (`UncoverFuture` and
`PaymentPlan`) into `NCrystalSphereScreen`. The smallest complete acceptance case
is entry, a legal tool state, all allotted reveals, earned reward resolution and
native map return. The original event callback remains owned throughout; reaching
zero divinations alone does not complete the event.

The dedicated `crystal_sphere_v1` child publishes an 11×11 row-major fog mask,
remaining divinations, selected small/big tool and legal actions. `reveal:N` uses
slot `y * 11 + x`; small reveals one cell and big reveals the bounded 3×3 area.
It publishes no hidden item models, positions, textures or RNG state. This first
projection also omits revealed-item artwork/geometry; it supports a simple legal
reveal policy rather than strategic board inference. The default policy chooses
the big tool and then the first legal hidden cell.

Each reveal invokes the exact native screen handler once and retains its Task.
Completion checks the exact fog/count/tool delta, cell/control identities and
unchanged unrelated player inventory. Native curse additions are witnessed through
the scoped `AddCursesToDeck` callback and its successful returned card identities;
an arbitrary appended Doubt does not count as that result. Tool selection uses the
native button. Neither path inspects or generates board rewards speculatively.

After the game actually offers earned rewards, the child exposes gold, card,
potion and relic rows through the existing public reward reader/applier. Cards
include their actual upgrade levels. Advertised actions are `reward:claim:N`,
`reward:collect:N`, `reward:open:N`, `reward:choose:N`, `reward:skip_card` and, when
needed, native reward-screen `dismiss`. Repeated reward indices retain stable
session ordinals. Collection and menu Tasks, exact gold/card/item effects and
unchanged unrelated inventory are reconciled before another action. Automatically
freed reward screens reconcile from retained models and results without traversing
retired Godot nodes.

Only successful reward completion and the original event callback admit the
parent `CRYSTAL_SPHERE.LEAVE` choice. Its native exit must finish with a fresh map. The native game retains the completed
sphere overlay when opening that map; parent-owned disposal removes only that exact
sole overlay through `NOverlayStack.Remove`, then verifies the empty stack, actionable
map and unchanged inventory before releasing ownership. Failed removal is never retried. A resolved sphere child is
not itself transport completion and is not counted as a completed card/item child;
its episode and action history remain tracked with parent effects `unverified`.
Lost mutation replies are never retried; unresolved disposal remains a failure.
The child is bounded to 40 actions and 512 native reads, within the existing host
and parent limits.

Static bindings use the same pinned game assembly as Fake Merchant. Admission requires
entry through an owned ordinary event choice; adopting an already-open sphere,
full-potion replacement and nested pickup selectors remain outside this path.
See the
[wire contract](../bridge/Sts2AgentBridge/components/events/wire/schema.md).

<a id="implemented-offline-trial-abandonment-confirmation"></a>

### Trial abandonment confirmation

Trial's Reject page mixes Accept with Double Down. In the pinned native code,
Double Down has `IsProceed=true`, `DisableOnChosen=false` and a lethal predicate,
but its exact callback only creates `NAbandonRunConfirmPopup` in `NModalContainer`.
It preserves the buttons and sets `WasChosen` before creating the popup. The bridge
recognizes only the single-cast private `OnChosen` delegate targeting
`Trial.DoubleDown` on the same model for this exception. Public candidates retain
the native flags and use discovery `abandon_confirmation`; other lethal options
remain blocked. This is a narrow native exception to ordinary deferred discovery,
not a general permission to dispatch lethal choices.

The owned child `abandon_confirmation_v1` offers Cancel first and explicit
`confirm_abandon`. Cancellation checks unchanged deck, HP, gold, potions, relics,
run/event ownership and the post-click option presentation, including exact
buttons, options, callbacks and labels. After native modal closure, the same
buttons receive fresh bridge bindings and a new decision; old receipts cannot be
reused. Cancel does not undo native `WasChosen` or earlier event effects.

Confirmation uses the popup's native Yes button in singleplayer and captures its
exact `RunManager.AbandonInternal` task. Resolution requires successful completion,
the same manager/run/player, `IsAbandoned=true`, player HP exactly zero and the
owned modal closed. Parent phase and final history result become `run_abandoned`.
This does not assert main-menu arrival, saved-history contents or map readiness.
Completed outcomes are checked again before reconciliation and owner release;
pending tasks, lost callbacks, replaced state and uncertain actions stop cleanup.
There are no mutation retries or direct save/profile operations.

The parent protocol is `generic_event_v10`; route names remain unchanged. The
bundled client defaults to cancellation; `--abandon-policy confirm` explicitly
selects termination. Use `--capability events` for this terminal path rather than a
stage whose acceptance condition requires a map.

### Architect terminal progression

The Architect’s terminal choice observes the native readiness vote, exact queued
vote action, `EnterNextAct` and `WinRun` tasks. Only their successful completion,
exact retained ownership/inventory and native win effect produce `run_won`.
Pending votes or win tasks remain waiting; foreign actions, altered state, failed
tasks and unresolved cleanup stop the host. No map read is required after `run_won`.

The implementation has a known live admission failure; see [status](STATUS.md).

<a id="separate-remaining-questions"></a>

## Source and evidence references

The [wire schema](../bridge/Sts2AgentBridge/components/events/wire/schema.md) owns
payload field definitions. [G7](archive/phase-1/PHASE_1_GENERIC_EVENT_V7_CONTRACT.md)
and the [V10 input experiment](archive/phase-1/PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md)
retain historical artifact semantics. [Static research](EVENT_INTERACTION_MAP.md)
identifies caller candidates; [status](STATUS.md#implementation-gaps-versus-remaining-live-tests)
separates current implementation gaps from live validation. Use the
[live guide](LIVE_DEVELOPMENT.md) for preparation, evidence reuse and cleanup.
