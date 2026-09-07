# Generic event handler: next development direction

Updated 2026-09-06 after the user clarified the intended meaning of all-event
support. This is a planning document, not an implemented or frozen contract.
It supersedes the caller-by-caller expansion priority; it does not change any
accepted component, source identity, protocol or live release.

## Reward-addition checkpoint — 2026-09-07

`generic_event_v3` adds shared reward requests followed by exact selected-original
additions, without event-name rules. Both automatic-at-max and explicit-confirm
modes support1..8 cards and variable limits. It binds effective result cards before
child actions, tolerates native sorting and monotonic partial additions, and
requires exact request/selector sets and parent success before completion. Read
its [contract](PHASE_1_GENERIC_EVENT_V3_CONTRACT.md) and
[ledger](research/PHASE_1_GENERIC_EVENT_V3_ACCEPTANCE.md). Extend remaining shared
families, including transformation, multi-upgrade and item children; optional,
scrolling and custom/combat interactions remain gaps. Release/live gates stay open.

## Removal and variable-count checkpoint — 2026-09-07

`generic_event_v2` retains upgrade-one and extends shared discovery to removal
with1..8 cards and variable limits. It replaces the parent's hardcoded child
semantics with an immutable native admission and verifies actual removal-preview
originals, task sets and remaining-deck identity. See its
[contract](PHASE_1_GENERIC_EVENT_V2_CONTRACT.md) and
[ledger](research/PHASE_1_GENERIC_EVENT_V2_ACCEPTANCE.md). Expand by remaining
shared families; packaging and live validation remain separate work.

## Implementation checkpoint

`generic_event_v1` implements the first complete standard interaction path:
upgrade-one discovery through owned event/request/screen-creation calls, actual
native card control, frozen reconciliation and a bounded C#-to-Python controller.
It requires no event-name registration. The
[successor contract](PHASE_1_GENERIC_EVENT_V1_CONTRACT.md) explicitly resolves
the two-stage timing conflict; the
[ledger](research/PHASE_1_GENERIC_EVENT_V1_ACCEPTANCE.md) records validation.
The remaining family/count/custom gaps below stay open; this checkpoint does
not mean every event or branch is supported or a live release is ready.

## What the user means

Build a controller that handles the interactions an event presents, so another
event using a supported interaction does not need a new event-name registration.
Events should primarily be representative and held-out tests of shared handlers.
Dedicated adapters may still be necessary for different custom screens,
minigames or event combat. Do not promise that a generic standard-screen handler
alone covers all events or every branch.

The previous implementation delivered useful shared mechanisms, but its exact
caller allowlist remained the gate to native card support. The latest work mixed
generic mechanisms with individual Aroma/Sapphire connections and Brain/Zen
research. It did not deliver automatic support for arbitrary events. Future
updates must distinguish shared mechanics, named native connections, release
availability and live evidence.

## Accepted implementation to reuse

At implementation commit `b2ae0dd6577e7d44c208252f816e2266391c2ea5`:

| Layer | Existing behavior | Remaining limitation |
| --- | --- | --- |
| Event parent | Bounded ordinary choices, sequential item/card children, parent receipts and explicit Proceed/map handoff | Unknown/custom transitions stop; card capability is selected from a closed caller registry |
| Card core | Add/remove/upgrade/transform semantics, explicit min/max counts, preview/confirmation, original-card identity and exact effect reconciliation | Generic fixture policies do not make native callers available |
| Native event card connection | Cheese/Gorge add-two-of-eight, Aroma/Maintain Control upgrade-one, Sapphire/Eat upgrade-one | Three exact event/key policies; no automatic interaction discovery |
| Host and wire | Immutable decision-provider seam, legal-action validation, shared budgets and correlated results | Production policy catalog is also closed, so changing only the native classifier is insufficient |
| Rest-site upgrading | Ordinary Smith upgrades exactly one card, demonstrated live in its predecessor release | Preserve this independently from variable-count event selection |

The event-card functional gate passes 675 checks across 19 suites. Its source
identity and all predecessors are frozen. Its new event upgrades are not packaged
or live-tested. Exact evidence is in the
[event-card ledger](research/PHASE_1_EVENT_CARD_OPERATIONS_V1_ACCEPTANCE.md).

## Architecture work needed before implementation

Investigate how to obtain an authoritative interaction description from the
game's public APIs or a narrowly reviewed integration point where the game
creates the interaction. Do not assume that such a complete description or
permitted hook already exists. A title, option label, screen class, apparent
card change or inferred event name is insufficient to establish semantics.

The proposed description needs, as applicable:

- operation and minimum/maximum selection count, including variable and multiple
  selections in events; ordinary Smith remains exactly one;
- actual cancellation, automatic submission and confirmation rules;
- the complete eligible/generated candidate domain with original object
  identities, ordered slots and authoritative selection-task identity;
- the parent event/option/accepted-action identity that owns the interaction;
- operation-specific completion and effect witnesses, including authoritative
  original-to-replacement mapping for transformation;
- a lifecycle that survives asynchronous setup and returns control to the same
  parent only after completion, without adopting a later replacement screen.

Keep event identity for ownership, correlation, diagnostics and coverage.
The design objective is to remove event identity as the semantic allowlist for
standard supported interactions, not to remove identity checks or validation.

The existing implementation distinguishes existing-deck and generated domains.
Existing-deck operations retain the complete baseline deck (at most 512 cards)
and eligible original references before the parent action. Generated operations
bind generation owner/inputs/count before dispatch; only the generated originals
are deferred to first complete admission. Preserve this distinction in the audit.
Do not allow clients or decision providers to inject native operation semantics.

### Resolve the pre-dispatch contract conflict explicitly

The frozen event-card contract requires the operation, selection limits and
expected candidate count to be bound before choosing the event option. A
runtime selector created after that choice cannot satisfy missing pre-dispatch
facts retroactively. The current catalog exists partly to supply those facts.

The next design must establish which facts are available before the choice and
which can only be captured when the game creates a child. If two-stage admission
is needed, specify it in a new versioned contract: reserve the parent action,
retain its pre-action baseline, obtain an authoritative child description at a
proved creation/dispatch boundary, then expose child actions. Account for event
effects that may occur before a selector appears. Do not claim that a later stop
means the parent action had no effect. Merely removing the allowlist or accepting
an arbitrary visible selector is not the proposed solution.

Any integration mechanism that needs new instrumentation or a wider observation
boundary must be concretely described and reviewed within the user's existing
event-development authority and restrictions. This planning document does not
select a hooking mechanism or broaden unrelated capabilities.

## Suggested execution sequence

1. Trace the current native registry, pre-dispatch binding, policy catalog and
   host/wire checks. List each fact currently supplied by a named policy.
2. Audit available selector/interaction creation APIs and retained static evidence
   to find an authoritative shared source for those facts. Record unavailable
   facts rather than reconstructing rules from labels or effects.
3. Review a successor contract covering discovery, admission, ownership, effects,
   public observations and budgets. Preserve all frozen source trees.
4. Implement one complete generic card-interaction path through actual native
   adapter, core, wire and host. Exercise multiple event identities with no new
   production event/key row. Then extend by interaction family.
5. Test add/remove/upgrade/transform and their supported count/confirmation modes,
   including asynchronous setup, same-object mutation, replacement, failure and
   uncertain actions. Keep optional selection, scrolling, repeated choices,
   custom layouts and event combat explicit until handled.
6. Prepare release composition only after functional integration passes. Ask the
   user for an exact live screen when the installable test is ready. Use several
   representative events and reserve held-out event identities for testing reuse.

The user previously requested parallel work. After the shared contract is clear,
separate native discovery, wire/host adaptation, fixtures and independent review
behind exclusive ownership. Do not dispatch one implementation task per event as
the default expansion strategy.

## Acceptance criteria for generic support

A supported standard interaction must work under multiple event identities,
including an identity absent from the production event catalog, without editing
an event-name/key allowlist. Exercise the real production discovery/admission
path against inert game stubs and the actual shared card session; a generic core
fixture supplied with a synthetic policy alone does not prove this property.

Operation, counts, candidate originals and task/effect ownership must come from
the reviewed authoritative boundary. Cover one-card and multi-card events, exact
confirmation behavior, and absence of cross-event or stale-child adoption.
Unknown interaction families must stop explicitly with truthful action/effect
accounting. Preserve no retry after an uncertain mutation, bounded work, reserved
receipts, complete domains and explicit final handoff.

Track implementation, native fixtures, release and live evidence separately in
the [coverage matrix](research/PHASE_1_EVENT_COVERAGE_MATRIX.md). The census of
68 concrete types includes ancient/deprecated types and does not establish the
reachable event pool or all-branch completion. Strategic choice quality and
natural encounter discovery remain separate from reliable interaction control.

## Retained research and open questions

Brain Leech's `FromCardChoiceCount` and exact add-one callback provide a useful
generated-card test case. Its
[future caller proposal](research/PHASE_1_EVENT_CARD_OPERATIONS_V1_NEXT_CALLER_SELECTION.md)
is retained evidence, not the next implementation assignment.

The [Brain/Zen result](research/PHASE_1_EVENT_CARD_FOLLOWUP_RESULT.md) proves Zen's
outer awaited completion and manual option/delegate bindings, but not the helper
argument-to-field mapping or the redacted callback dynamic keys. Do not label the
constants 1/2 as removal counts or costs without that mapping.

The [preview result](research/PHASE_1_EVENT_CARD_PREVIEW_RESULT.md) does not prove
that multi-upgrade preview clones expose their original through `CloneOf`.
Transformation replacement mapping is also open. The generic design must solve
these shared identity questions rather than treating similar card definitions as
interchangeable originals. Retained metadata is static evidence, not a live corpus.
