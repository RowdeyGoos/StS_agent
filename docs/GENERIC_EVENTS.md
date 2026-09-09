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

## Next acceptance case: one card enchantment

Generic event interactions now take priority over longer-run orchestration; the
[roadmap](../ROADMAP.md) owns that order. Card enchantment is the next concrete
implementation target. Sapphire Seed's observed Plant and Nourish option enchants
a card with Sown and remains unsupported. Retained metadata-only inspection of
the pinned game also shows `FieldOfManSizedHoles.EnterYourHole` requesting exactly
one card through `CardSelectCmd.FromDeckForEnchantment`, applying `CardCmd.Enchant`
and finishing the event. The current generic hooks do not bind that request.

The smallest acceptance case is to bind that shared request and its actual native
selector, choose one eligible original card once, verify the requested enchantment
on that exact card, then resume the parent through Proceed and verify core map
readiness. Check existing enchantments, ineligible/changed targets, failed tasks
and cleanup at the relevant boundaries. Reuse existing parent ownership,
transport and selection mechanisms where their semantics apply. Enchantment
identity/effects need explicit observations; an upgrade-level check is insufficient.
This is a selected implementation target, not implemented or live-tested support.

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
