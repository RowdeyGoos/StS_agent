# Phase 1 event-card candidate caller selection

- Date: 2026-09-06
- Status: retained future candidate; not the active implementation priority;
  absent from the frozen three-row component
- Selected caller: `BrainLeech.ShareKnowledge()`
- Proposed policy ID: `brain_share_knowledge_add_one`
- Exact event option key:
  `BRAIN_LEECH.pages.INITIAL.options.SHARE_KNOWLEDGE`
- Retained callback diagnostic result SHA-256:
  `e8c6f9aad5035daa21e7329b89669c652c9845ae07049d9f1274b1cd26c762ca`
- Brain/Zen follow-up result SHA-256:
  `8fd76338f6b6eb64aa1063fa24b5cf77fd66fbaeec062af234bea09186e7cfe9`

## Current priority clarification

The user subsequently clarified that generic interaction discovery should be the
next development focus. This named-row proposal is retained as evidence and a
representative add-one test case. It is not an assignment to implement Brain
before that shared design. Follow the
[generic handler plan](../PHASE_1_GENERIC_EVENT_HANDLER_PLAN.md); the remaining
policy/admission details below describe this candidate's semantics only.

## Selected policy

The proposed Brain Leech Share Knowledge candidate has the following policy:

- exact runtime event type `MegaCrit.Sts2.Core.Models.Events.BrainLeech`;
- exact stable event identity admitted by the event parent;
- the exact `SHARE_KNOWLEDGE` option key above and its exact bound option,
  controller and callback;
- operation `Add`;
- minimum and maximum selected cards `1`;
- commit mode `AutoAtMax`;
- domain source `GeneratedAtAdmission`;
- supported domain count `2..64`;
- exact predispatch dynamic-variable key `FromCardChoiceCount` and value equal
  to the later admitted child domain count.

The exact initial option set must contain both
`BRAIN_LEECH.pages.INITIAL.options.SHARE_KNOWLEDGE` and
`BRAIN_LEECH.pages.INITIAL.options.RIP`, each bound to its exact callback, with
no extra or duplicate option. `RIP` remains known but unsupported. The event,
options and controllers must have exact runtime types; subclasses are rejected.
No other Brain Leech option, event type, generated-card caller or dynamic key is
selected.

## Static basis

The exact initial-options body constructs two options and directly binds
`SHARE_KNOWLEDGE` to `ShareKnowledge()`. The exact attributed callback body:

1. reads `DynamicVars["FromCardChoiceCount"].IntValue`;
2. passes that integer to `CardFactory.CreateForReward` and materializes the
   returned creation results;
3. constructs noncancelable card-selector preferences with minimum and maximum
   1;
4. awaits `CardSelectCmd.FromSimpleGridForRewards`;
5. takes the selected `CardModel` with `FirstOrDefault`;
6. awaits one `CardPileCmd.Add` to the deck, previews the add, and calls
   `SetEventFinished` on the same event.

The retained helper body returns without a selector when the generated list is
empty or, with manual confirmation false, when its count is at most the minimum.
For this row, requiring the captured count and later exact domain to be at least
2 excludes that selectorless path. The already accepted Room Full of Cheese
path supplies the same `NSimpleCardSelectScreen`/`NCardGrid` local-selection
surface and selected-`CardModel` return boundary, but does not by itself bind a
Brain row.

## Required native admission

Before dispatch, the native parent must capture and retain the exact run,
player, event room, map, exact Brain Leech instance, both exact initial options
and controllers, and `FromCardChoiceCount` dynamic-variable identity and
integer. It must copy the complete baseline deck, bounded to 512 exact unique
card references, before dispatch. It must also retain the exact generation
owner, `Player.Character` and that character's exact single `CardPool` reference
used at IL 56--78, and bind the reviewed
`ForNonCombatWithDefaultOdds(singlePool, null)` creation rule. It must require
the dynamic value to be `2..64`, bind that value into the accepted policy, and
reject a missing, changed, out-of-range or noninteger value without dispatch.
The dynamic-variable object/value, owner, character and card-pool references are
recaptured before dispatch and again at child admission.

After the accepted parent receipt, child admission must require:

- the first foreground selector is the sole overlay and exact
  `NSimpleCardSelectScreen` runtime type expected by the retained helper;
- `CardSelectCmd.Selector` is null before parent dispatch and remains null
  throughout the reviewed local overlay path; the test-only selector override
  is not the production screen identity;
- the exact `%CardGrid` runtime type, stable geometry and no partial, scrolling
  or animating page;
- a complete ordered list of exactly the captured domain count, with unique
  valid holder, card, hitbox, highlight and `CardModel` references;
- one fresh completion task, no already-selected candidate and no unrelated
  deck change.

The first admitted screen, grid, holders, card models, task and captured parent
references become lifetime bindings. Disappearance before readiness,
replacement, reorder, duplicate identity, page/geometry change, a second
selector, a changed dynamic value or option/controller drift terminates the
child without adopting later state.

## Completion and negative fixtures

The child may dispatch one exact visible, enabled, settled candidate. It must
match the returned `CardModel` by reference, observe exactly one awaited deck
addition of that model, preserve all prior deck entries, and then observe the
same Brain Leech instance become finished before returning control to the event
parent. Failure, cancellation, empty/multiple results, a different added card,
an extra deck mutation, finish-before-effect or effect-without-finish is
unsupported and terminal. The event parent then follows its existing explicit
Proceed/map handoff.

Actual-source inert fixtures must cover both count boundaries (`2` and `64`),
`0`, `1` and `65`, count drift before and after dispatch, baseline-deck and
generation-reference drift, selectorless direct completion,
incomplete/scrolling grids, wrong exact types, replacement and same-object
mutation, stale/replayed receipts, uncertain dispatch, rejected action replay,
idempotent disposal and the full selected-card-to-add-to-finished sequence.
Cross-language fixtures must bind the public `child_domain_count`, candidate
order, one legal slot, exact auto-at-max history and resolved payload.

## Acceptance boundary

This record selects the next row and its gates. It does not modify the accepted
three-row catalog, authorize implementation in a frozen component, claim that
the native surface already satisfies the new guards, or provide release/live
evidence. The row belongs in a separately derived successor and remains absent
until its actual native adapter, derivation record and aggregate pass are
independently accepted.
