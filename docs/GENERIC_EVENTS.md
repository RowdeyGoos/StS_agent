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
complete two and eight selections through Proceed/map. These are offline
implementation checks; Prickly Sponge and other multi-card callers have not yet
been live-tested. Optional counts, stacking/replacement and ancient-layout entry
remain separate gaps.

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
lost replies and cleanup interference. These capabilities are implemented
in source; the current accepted release and its live evidence still describe the
previous removal build. Packaging and live acceptance will follow the planned
batch test session.

## Implemented: ordinary event card reward menus

`card_reward_v1` adds a `card_reward` child for one populated, unlinked, exact
`CardReward` in an owned nonterminal `RewardsSet.Offer`. The representative pinned
caller is **BrainLeech/Rip** (canonical RewardCount one); **TheFutureOfPotions/Trade**
also offers one reward and upgrades its generated cards before opening the screen.
These are source-backed acceptance candidates; neither caller has live acceptance
for this increment. The Cheese add-card grid remains a separate interaction.

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
not yet packaged or live-accepted. The multiple-entry extension is described below.
Mixed card/item sets, repeated offers within one option, SpecialCardReward, reroll/multiple picks,
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
cannot collect early. Duplicate rewards/models, mixed card/item sets, linked or
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
Philosophers remains a live acceptance candidate. Mixed card/item sets, repeated
Offers within one option, SpecialCardReward, rerolls/multiple picks, substituted
cards and nested pickup selectors remain separate gaps.

## Separate remaining questions

An allocated off-screen holder can accept direct input. A card without an
allocated holder cannot use that path yet. Incomplete coverage may require
scrolling/rebinding or another supported native mechanism; inspect that specific
case before designing infrastructure. Other selector families may still impose
layout restrictions and need their own evidence.

The [all-event research map](EVENT_INTERACTION_MAP.md) now records branch families
for all 68 pinned types and concrete callers for the remaining work. Repeated-page
progress and pre-selector append-only additions are implemented above. Deck
changes after selectors, other pre-selector deck mutations, mixed card/item reward sets and broader pickup composition, ancient and
combat layouts, optional/sequential pickup children and custom
surfaces are distinct gaps. WoodCarvings uses a generic deck selector before a
fixed-result transformation; it does not enter the supported transform screen.

Choose the next feature from those source-backed callers. Positive variable
transformation already works offline; Claws supplies a concrete optional zero-to-six
caller through Tanx, with ancient layout and zero-selection prerequisites. No
inspected event/immediate pickup establishes variable-count upgrades or true native
cancellation. Keep those speculative extensions separate from demonstrated gaps.

For semantic detail use [G7](archive/phase-1/PHASE_1_GENERIC_EVENT_V7_CONTRACT.md), the
[v10 input experiment](archive/phase-1/PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md) and the
[coverage matrix](EVENT_COVERAGE.md).
For preparation, evidence reuse and cleanup use the [live guide](LIVE_DEVELOPMENT.md).
