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
These are inert fixtures, not execution of Amalgamator's native body. The next
live case is CombineStrikes with at least three eligible Strikes,
select exactly two, confirm their preview, then observe the grant and fresh map.
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
unenchanted; stacking, replacement, multiple selection and cancellation are
unsupported. The request binds canonical enchantment identity, public key,
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

## Separate remaining questions

An allocated off-screen holder can accept direct input. A card without an
allocated holder cannot use that path yet. Incomplete coverage may require
scrolling/rebinding or another supported native mechanism; inspect that specific
case before designing infrastructure. Other selector families may still impose
layout restrictions and need their own evidence.

The [all-event research map](EVENT_INTERACTION_MAP.md) now records branch families
for all 68 pinned types and concrete callers for the remaining work. Repeated-page
progress and pre-selector append-only additions are implemented above. Deck
changes after selectors, other pre-selector deck mutations, event card/multiple rewards, ancient and
combat layouts, multi-enchantment, optional/sequential pickup children and custom
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
