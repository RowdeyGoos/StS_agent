# Generic event development

[Current status](STATUS.md) owns supported capabilities and latest
evidence. [AGENTS.md](../AGENTS.md) owns the streamlined workflow.
This document describes the architecture and next acceptance case, not campaign history.

## Implemented architecture

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

This two-stage admission is implemented. Do not restart discovery design from
the old proposals. G7 and inherited child contracts describe exact semantics;
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

## Implemented: appended cards before a selector

The first owned card-selector request can establish a deck baseline that includes
cards appended by the preceding event callback. The original pre-action deck must
remain an exact prefix: identical card objects, order, keys, upgrade levels and
enchantment identities/values. New cards must belong to the same player and run;
the complete deck remains bounded at 512 cards. Binding happens once, before
native selector creation, with the existing parent ownership and empty-overlay
checks. Prepending, replacing, removing, reordering or modifying original cards
is unsupported in this increment.

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

Pinned callers are Grave of the Forgotten/Confront (Decay before single-card
SoulsPower), Trial/MerchantInnocent (Shame before two upgrades), and
Trial/NondescriptInnocent (Doubt before two transformations). The pinned
`AddCursesToDeck` path uses the deck append position. Inert fixtures cover these
interaction shapes, the other shared selector families, selection of an eligible
newly appended card, delayed requests, changed originals, late additions,
ownership loss and collateral enchantment changes. Native-to-host cases complete
the three representative shapes through Proceed/map. The enchantment fixture
uses Sown and does not execute Grave's native body. Separately, Grave/Confront
passed live on release `65c4e3d526b799f53795ab77131ba8947ad42be1db7f8261c1cacb064fe52dc9`:
SoulsPower amount 1 on unupgraded Neow's Fury, slot 0 of 3 eligible cards, exact
preview/effect, Proceed and independently verified core map. All four actions
reconciled. This exercises the native curse-before-selector caller; automatic
addition provenance is still outside the child effect guarantee. Trial verdicts
remain separate caller tests. See the
[live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#seventh-installation-repeated-pages-and-pre-selector-additions).

## Implemented: removal followed by one appended grant

Generic removal children now advertise **`card_remove_v2`** before input. The
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

The concrete pinned caller is **Amalgamator/CombineStrikes** (two removals followed
by an appended Ultimate Strike); CombineDefends follows the same shape with
Ultimate Defend. Native fixtures cover immediate and delayed callbacks,
pre-selector plus post-removal additions, exact survivors and invalid suffixes;
producer-to-Python cases check separate grant metadata through Proceed/map.
These fixtures are inert. Separately, the September 9 live CombineStrikes test
passed with five eligible cards: upgraded Strikes at slots 0 and 1 were removed
after exact preview, one upgraded Ultimate Strike was reported with unverified
parent provenance, and Proceed returned to a fresh actionable core map. All five
actions reconciled. CombineDefends, other callers and off-screen removal remain
untested live. The [live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#tenth-installation-native-removal-without-whole-grid-geometry)
retains the exact release and result.
Multiple grants, interleaved/prepended additions, other post-selector operations
and changes to surviving cards remain unsupported.

## Implemented: repeated ordinary option pages

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

Inert native-to-host fixtures exercise Immerse → Linger twice → Exit → Proceed/map,
identical text, revisited keys, delayed/failed callbacks, stale/partially replaced
controls, dangerous choices and action limits. Existing item-child cases also
reuse a parent key across separate completed children. These are offline checks.
Abyssal Baths passed live on release `65c4e3d526b799f53795ab77131ba8947ad42be1db7f8261c1cacb064fe52dc9`:
Immerse, two Lingers, Exit Baths and Proceed all reconciled, followed by an
independently verified actionable map. See the
[live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#seventh-installation-repeated-pages-and-pre-selector-additions).
Endless Conveyor and Slippery Bridge remain separate caller tests.

## Implemented: all eligible transform holders

The successful v10 experiment directly selected an allocated off-screen card.
Its card16-only mask and dispatch guard were test restrictions. The unified
production bridge now uses the generalized adapter in
`bridge/Sts2AgentBridge/components/events/native/GenericEventV7TransformAdapter.cs`.
Historical release evidence remains in Git.

- Both fixed-slot restrictions are removed. All legal allocated holders are
  exposed in native order, with complete candidate/domain binding.
- Retain exact holder/model/run/screen/task ownership, native enabled state,
  deferred-callback identity, exact-original preview membership and selected-only
  transformation reconciliation. Matching card names do not establish identity.
- Keep viewport, clipping-parent and complete-layout-fit checks out of this
  direct transformation input path. The earlier ten-card suggestion is obsolete.
- Keep fixed/variable preview semantics and host decision-provider behavior.
  Do not change strategy or add event-name admission rules.

Acceptance exercises actual adapter-to-client selection of different targets,
including visible and allocated off-screen holders. It rejects missing, disabled
or reassigned targets without choosing a substitute or retrying uncertainty, and
checks existing preview/completion modes. Reuse matching accepted dependency
evidence; one independent review addresses the changed action semantics.

A further live test must answer a remaining behavior question, such as selecting
another advertised target through the generalized path. Use the minimal known
setup and one precise expected outcome. Do not repeat the same card16 question
with another visibility-proof implementation.

The generalization is implemented and tested offline. The direct-input fixtures
exercise slots 0, 15 and 19 in a 20-card domain and slot 1 in a two-card domain,
plus missing/disabled/reassigned targets and deferred input. Existing fixed and
variable transformation regressions remain. A new live all-holder claim has not
been made; see [current release evidence](../bridge/Sts2AgentBridge/releases/current/README.md).

## Implemented: allocated upgrade holders

Generic fixed-count upgrades (1–8) now use their existing direct holder input
without requiring the entire eligible grid to fit inside the viewport. The exact
allocated domain remains bounded at 64 cards; unallocated cards are unsupported.
The adapter retains holder/model/card/hitbox identity, native `_isClickable` and
hitbox enabled state, settled highlights, exact preview originals (or mapped
multi-upgrade clones), task results and selected-only deck effects. Multi-upgrade
input retains its dispatch ticket through the deferred native callback. Scroll
position and viewport size are not target identity.

The pinned `NCardHolder._GuiInput` checks `_isClickable` before deferring
`EmitPressed` on that holder. Inert native fixtures exercise slots 0, 15 and 19
in a 20-card domain, viewport changes, rejected target mutations and deferred
multi-upgrade selection. Native-to-Python fixtures verify later-card selection,
exact deck effects, Proceed and map return. These are offline checks, not live
proof of upgrade behavior below the viewport.

The September 9 [live batch](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md)
demonstrated `SapphireSeed`/Consume with 23 eligible cards: direct selection of
unupgraded Defend slot 20 below the viewport, exact preview and upgrade effect,
Proceed and an independently checked core map. No selector scrolling or manual
card input was used. This establishes one allocated off-screen single-upgrade
path; multi-upgrade and other domains/counts remain separate evidence targets.
For console fixtures, check automatic-upgrade relics and actual card eligibility:
Molten Egg upgraded the added Bashes; unupgraded Defend skills supplied this case.

## Implemented: one card enchantment

The shared `CardSelectCmd.FromDeckForEnchantment` request and
`NDeckEnchantSelectScreen` now form a `card_enchant_v1` child of the existing
`generic_event_v7` parent. No event-name admission rule is added. Sapphire Seed's
observed Plant and Nourish branch is the representative live target. Pinned
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

Native fixtures cover distinct event identities, copied/sorted request lists,
preview and effect replacement, collateral changes, failed/delayed completion and
unsupported request shapes. Native-to-Python checks cover selection through
Proceed/map return, a later allocated target, delayed completion and wrong effects.
The [sixth live installation](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#sixth-installation-single-card-enchantment)
passed Plant and Nourish: Sown amount 1 on unupgraded Defend slot 5 of 24,
exact preview/effect verification, Proceed and the shared client's independently
checked core map. All four actions reconciled; normal quit and owned cleanup
passed. Other enchantments/callers and broader selection semantics remain unproved.

## Implemented: fixed multi-card enchantment

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

Native fixtures cover counts two, three and eight, deferred final input,
replacement targets/previews, partial effects, shared/replaced/disappearing
enchantments and collateral changes. Actual C# wire/Python controller fixtures
complete two and eight selections through Proceed/map. Prickly Sponge now also
has live acceptance: two upgraded Strikes in a 24-card eligible domain, exact
original preview, Steady amount 1 on each and an independent fresh core map.
All five actions reconciled. See the [live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#prickly-sponge-fixed-two-enchantment-passed).
Other enchantment counts/callers, optional counts and stacking/replacement retain
their narrower evidence or remain gaps. Ancient entry now has offline support below.

## Implemented: multiple potion/relic rewards

One owned, nonterminal `RewardsSet.Offer` may now yield 2–8 populated, unlinked
potion/relic entries. The new generic item child uses `item_set_v1`; a singleton
keeps `item_v1`. Whispering Hollow/Gold (two potions) and War Historian Repy's
Unlock Chest (two potions and two relics) supply representative native shapes.
This is the ordinary item-reward screen, distinct from event card-reward menus.

The child collects entries in their original generated-list order. Each entry
retains its exact reward/model identity, native type index and control. Public
`collect:N` indexes are zero-based **list positions** within the set: the game's
`RewardsSetIndex` identifies a type and can repeat for two potions or two relics.
Duplicate offered model identities, linked rewards, unsupported reward types,
foreign controls and changed list membership/order are rejected. All potion
entries must fit in the initially free slots before the first collection; this
increment does not add discard/replace/skip behavior for full inventory.

Each entry uses the existing `item_v1` observation/action/effect checks. Its
collection task must succeed before advancing. Completed entries retain their
selected flag, exact claim, collection task and potion slot across subsequent
entries. The initial potion inventory and capacity remain fixed apart from the
verified insertions. The last collection also waits for the original Offer and
Chosen tasks and automatic closure of the owned reward screen. Native rewards
stay in the list after collection; removed/freed completed buttons are allowed.
Relic substitution, nested pickup selectors and inventory-changing pickup effects
remain unsupported by the existing exact-effect boundary.

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

Offline native and C#/Python fixtures cover two potions, mixed sets, eight relics,
delayed tasks, late changes to completed claims/slots, malformed public history,
lost replies and cleanup interference. Potion Courier/Grab Potions now has live
acceptance: three Foul Potions collected in order, each exact inventory effect
reconciled, parent completion and an independent fresh core map. All five actions
reconciled. See the [live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#potion-courier-three-item-reward-set-passed).
Other counts, relic-containing sets and full-inventory behavior retain their
narrower evidence or remain gaps. [Current status](STATUS.md) owns the release and
installation identity.

## Implemented: ordinary event card reward menus

`card_reward_v1` adds a `card_reward` child for one populated, unlinked, exact
`CardReward` in an owned nonterminal `RewardsSet.Offer`. The representative pinned
caller is **BrainLeech/Rip** (canonical RewardCount one); **TheFutureOfPotions/Trade**
also offers one reward and upgrades its generated cards before opening the screen.
BrainLeech/Rip now has live acceptance: Equilibrium selected from slot 0 of three
offers, exact deck insertion, all four actions reconciled and fresh core map.
TheFutureOfPotions/Trade remains a source-backed caller candidate. The Cheese add-card grid remains a separate interaction.

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

Offline native fixtures and the actual C#/Python path cover single and five-card
menus, duplicate-key originals, both outcomes, delayed/deferred completion,
changed targets/owners/deck effects, native Skip legality, nondefault alternatives,
malformed replies, lost replies and rollback of either new hook. This code is
packaged in the current combined test release. Brain Leech's choose path passed
live; singleton Skip/dismiss retains offline evidence. See the
[live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#brain-leech-singleton-card-reward-passed).
The multiple-entry extension is described below.
Mixed card/item sets use the versioned extension below. Repeated offers within one option, SpecialCardReward, reroll/multiple picks,
hook-substituted cards and nested pickup selectors remain unsupported.

## Implemented: multiple card reward menus

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

Offline fixtures cover two, three and eight rewards with varied one/three/five-card
menus, all-collected, mixed and all-skipped outcomes, delayed collection/parent
tasks, native dismissal legality, changed admission and prior-effect state,
unsupported domains, malformed replies, lost replies and reentry. Colorful
Philosophers now has live acceptance through its Necrobinder option: three menus,
Fear+ from the first, native Skip in the second, Necro Mastery from the third,
final dismissal and an independent fresh map. All nine actions reconciled. See
[the live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#colorful-philosophers-multiple-menus-and-skip-passed).
Other counts and all-collected/all-skipped paths retain offline evidence.
Mixed card/item sets use the versioned extension below. Repeated
Offers within one option, SpecialCardReward, rerolls/multiple picks, substituted
cards and nested pickup selectors remain separate gaps.

## Implemented offline: mixed card/item reward sets

`mixed_reward_set_v1` extends the existing set session to **2–8 ordinary card,
potion and relic rewards in one owned nonterminal RewardsSet**, with at least one
card and one item. The pinned concrete caller is **LostCoffer.AfterObtained**:
its generated list contains a three-card CardReward followed by a PotionReward,
passed to `RewardsCmd.OfferCustom`. Lost Coffer is offered by Neow; reaching that
pickup through Neow can now use the ancient layout support below. The mixed-set
fixtures cover the shared reward surface; a full live Lost Coffer route remains
unverified.

Entries retain generated-list order. Cards use `open:N`, `choose:N:S` and legal
`skip:N`; items use `collect:N` through the existing item adapter and exact native
collection task. Each item settles after its collection succeeds and its exact
model/claim effect is verified. Offer and Chosen completion belong to the whole
set. If any card was skipped, the exact root Proceed control provides one final
`dismiss`, including when the last entry is an item. Otherwise native automatic
closure applies. Item Skip and full-inventory replacement are not part of this
contract; enough potion slots must be free for the whole set before first input.

The admission deck remains fixed through leading items. Only verified card
insertions advance its baseline. Initial potion slots plus verified insertions,
settled item claims, assigned slots and collection task identities remain valid
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

Native and C#/Python fixtures cover card→potion, potion→card, potion→card→potion,
eight mixed entries, choose/Skip/final dismissal, actual collection/Offer/Chosen
delays, failed collections, retained deck/inventory/task changes, insufficient
capacity, malformed replies, lost replies and item reentry/cleanup interference.
The production response classifier and shared request parser are included in
these checks. This source increment is unreleased and has no live acceptance;
the current release and previous live evidence retain their original identities.

## Implemented: generic deck transformation selectors

`FromDeckGeneric` with the native transformation prompt now admits a fixed-one,
noncancelable `NDeckCardSelectScreen` child. WoodCarvings/Bird and Torus are the
representative pinned callers: they filter transformable deck cards, show this
original-card preview, then call `TransformTo<Peck>` or
`TransformTo<ToricToughness>`. That command forwards through the existing observed
batch transformation path. The eleventh installation passed Bird on upgraded
Strike slot 0 of 21 eligible cards: exact preview, journal-verified transformation,
completed parent and fresh actionable core map. Torus remains a live candidate;
[status and the live record](STATUS.md) retain the result and scope.

Admission uses the native prompt's localization table/key (`card_selection` /
`TO_TRANSFORM`), not event names or rendered English. The prompt classifies intent;
it does not prove the eventual effect. The screen's filtered/sorted original list
is authoritative: 2–64 distinct, owned, transformable baseline cards with exact
allocated holder bindings. The bridge does not rerun filter or sorting callbacks.
Other prompts, optional/multiple selection, cancellation and selectorless automatic
completion remain outside this increment. The existing removal request's nested
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

Offline cases exercise Bird/Peck, Torus/ToricToughness and a held-out replacement,
filtered/reversed domains, original-only previews, delayed creation/selection/
command/parent completion, prompt/domain/legality/preview mutations, wrong request
results, failed commands, unrelated deck additions and removal forwarding. Actual
native-to-wire-to-Python cases also cover both named replacement shapes, callback
failure and a lost confirmation reply without retry. The Bird case now has representative live acceptance. Torus with at least two
eligible cards remains a distinct branch candidate. The live summary does not
expose the replacement key; the user separately confirmed Peck in the deck.

## Implemented offline: ancient dialogue and optional selections

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
The initial Sea Glass live attempt exposed the leftover layout prerequisite and
stopped before any card input. The corrected **Sea Glass zero-selection path has
live acceptance**: explicitly confirmed empty result, unchanged deck and fresh map.
**Three-card selection also passed**, adding the exact unupgraded Twin Strike,
Sword Boomerang and Tremble originals and verifying a fresh map. **All fifteen
selected cards also passed**, with exact additions, 18 reconciled actions and a
fresh map. These establish zero/partial/full examples, not every grid layout. See the
[live record](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#sea-glass-zero-passed-after-read-only-startup).

**Claws zero-selection has live acceptance**: explicit empty Preview/Confirm,
unchanged deck, four reconciled actions and a fresh map. **Three-card Claws also
passed**: three unupgraded Strike originals, explicit preview and seven reconciled
actions through exact native replacement checks and map return. Replacement names
are not exposed in the public result. Full selection remains pending. The native
zero-selection completion includes the required successful
empty transform command described above. See the
[live evidence](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#claws-zero-transformation-passed).

Optional behavior is enabled only by an explicit event context. Existing positive
selection versions, standalone card contracts and their limits remain unchanged.
Host and production boundary validation require the new matching descriptor and
payload versions; confirmed histories and exact selected sets remain mandatory.
Fixtures cover ancient entry, post-pickup dialogue reset, zero/partial/full counts,
small transform domains, delayed completion, stale input, malformed versions/results
and lost replies without retry. This is offline evidence, not live acceptance or
support for every ancient pickup. Full inventory,
nested pickups, cancellation and empty candidate domains remain outside this change.

## Implemented offline: choose-one cards and bundles

Two native selection surfaces now compose with the same event parent, including
ancient dialogue/options and Proceed/map. Representative pinned callers are
**Neow/LeadPaperweight** and **MassiveScroll** (choose one offered card), and
**Neow/ScrollBoxes** (choose a bundle). Admission uses the owned request/screen
chain and native models, without an event or relic allowlist.

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

This increment has native, production-boundary and C#/Python fixture evidence;
**live acceptance is pending**. These v1 contracts do not add Skip, preview
cancellation, extra grants/copies, card substitution or nested pickups. Optional
choose-one offers and one extra grant now have the separate v2 contract below.
Native direct menus with more than three choices are rejected.

## Implemented offline: optional card offers and one appended grant

`card_offer_v2` extends the direct ChooseACard family only when the owned native
request has `canSkip=true`. **Neow/HeftyTablet** is the representative caller:
its pinned `AfterObtained.MoveNext` passes true at IL185–186, creates Injury at
IL313, inserts the chosen card at list index zero only when non-null at IL324–340,
and awaits enumerable `CardPileCmd.Add` at IL350. Choosing therefore adds the
selected original followed by Injury; Skip still adds Injury. Admission remains
generic, with no event/relic allowlist. Other optional requests may add no extra.

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

Native fixtures, strict C#/Python integration and production-boundary checks cover
choose/Skip with and without the extra, delayed completion, changed controls/decks,
extra-card substitution/rollback, mismatched task results and lost replies.
**Both HeftyTablet branches have representative live acceptance**: choose added
Cruelty (unupgraded) plus Injury; Skip added Injury only. Each completed one card
child and reconciled three actions through a fresh actionable map. See the
[live evidence](evidence/COMBINED_BRIDGE_LIVE_2026_09_09.md#heftytablet-skip-passed).

## Implemented offline: inactive combat layouts and result acknowledgment

The parent now admits the pinned `NCombatEventLayout` while `HasCombatStarted`
is false and its native embedded room remains valid and unchanged. Ordinary
options and existing children use the same ownership and completion rules.
**PunchOff/Nab** is the representative interaction: Injury is added before the
singleton relic reward, then Proceed returns to map. **TheLanternKey/ReturnTheKey**
is another source-backed noncombat candidate. Layout admission does not implement
combat execution or return from combat. If a choice starts combat, this handler
stops as unsupported rather than reporting a map handoff. Native options do not
expose a reliable pre-choice combat flag, so this increment does not classify
all combat-starting choices in advance. Actual live acceptance is pending.

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
remain unsupported. Both new paths have offline native/C#/Python and production
boundary evidence; no live launch or installation was performed.

## Separate remaining questions

An allocated off-screen holder can accept direct input. A card without an
allocated holder cannot use that path yet. Incomplete coverage may require
scrolling/rebinding or another supported native mechanism; inspect that specific
case before designing infrastructure. Other selector families may still impose
layout restrictions and need their own evidence.

The [all-event research map](EVENT_INTERACTION_MAP.md) now records branch families
for all 68 pinned types and concrete callers for the remaining work. Repeated-page
progress and pre-selector append-only additions are implemented above. Deck
changes after selectors, other pre-selector deck mutations, broader pickup composition, combat execution/resumption, repeated/nested pickup children and custom
surfaces are distinct gaps. WoodCarvings’ generic deck transformation selector
is implemented above; Bird passed live, while Torus remains a branch candidate.

Choose the next feature from those source-backed callers. Positive variable
transformation and optional Claws selections are implemented. Claws zero-selection
and partial selection have live acceptance; its maximum-count branch remains pending. Sea Glass has zero/partial/full live acceptance through its
ancient route; other native ancient routes remain candidates for testing. No
inspected event/immediate pickup establishes variable-count upgrades or true native
cancellation. Keep those speculative extensions separate from demonstrated gaps.

For semantic detail use [G7](archive/phase-1/PHASE_1_GENERIC_EVENT_V7_CONTRACT.md), the
[v10 input experiment](archive/phase-1/PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md) and the
[coverage matrix](EVENT_COVERAGE.md).
For preparation, evidence reuse and cleanup use the [live guide](LIVE_DEVELOPMENT.md).
