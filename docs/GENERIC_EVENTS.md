# Generic event development

[Current status](STATUS.md) owns supported capabilities and latest
evidence. [AGENTS.md](../AGENTS.md) owns the streamlined workflow.
This document describes the architecture and next acceptance case, not campaign history.

## Implemented architecture

Handle shared interactions using the rules the game supplies. A new event using
a supported interaction does not need an event-name registration. Event names
identify ownership and representative/held-out cases; custom surfaces may need
separate adapters.

The parent reserves the chosen option and pre-action deck. Owned native request
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
These are offline results. The live acceptance case remains: Plant and Nourish,
one eligible original, exact Sown preview/effect, then Proceed and the shared
client's independently checked core map decision.

## Separate remaining questions

An allocated off-screen holder can accept direct input. A card without an
allocated holder cannot use that path yet. Incomplete coverage may require
scrolling/rebinding or another supported native mechanism; inspect that specific
case before designing infrastructure. Other selector families may still impose
layout restrictions and need their own evidence.

Further work includes optional/zero selection and cancellation, variable-count
upgrading, multiple-item reward sets, custom/repeated choices and event combat.
Choose the next family from a real representative caller or observed play blocker.
Positive variable transformation already works offline; the inspected live caller
used a fixed count. Do not invent a live test from the selector API alone.

For semantic detail use [G7](archive/phase-1/PHASE_1_GENERIC_EVENT_V7_CONTRACT.md), the
[v10 input experiment](archive/phase-1/PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md) and the
[coverage matrix](EVENT_COVERAGE.md).
For preparation, evidence reuse and cleanup use the [live guide](LIVE_DEVELOPMENT.md).
