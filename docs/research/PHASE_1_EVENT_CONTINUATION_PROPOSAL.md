# Phase 1 event continuation and public option observation proposal

- **Task:** `MR-EVENT-03`
- **Date:** 2026-09-05
- **Status:** proposed; not frozen, implemented, fixture-passing, or live-accepted
- **Baseline:** `68c8b50eed05d5442c66cc55f9ec9cf0513c7009`
- **Current bridge:** `0.8.0`, protocol `live_probe_v0`, schema `1`
- **Evidence used:** repository source, checked-in synthetic fixtures, and
  sanitized checked-in research only
- **Write boundary:** this document only

This proposal specifies the event-parent side of a later contract. It does not
change D47, enable a control, reconstruct the last live response, explain the
historical timeout, or claim that the visible loot surface caused the latest
`room_state_unsupported`. Item collection, replacement, decline, and skip
semantics belong to `MR-LOOT-02`; this document requires only a future typed
item-child interface from that lane.

## 1. Proposed outcome

The smallest useful successor should do two things together:

1. expose bounded text that is actually rendered to the player for each
   visible standard-event option, while continuing to expose the current key
   and flags; and
2. retain one event parent across accepted waiting, changed or resumed event
   choices, and explicitly typed child or exit handoffs.

It should **not** claim structured costs or effects. The repository establishes
no authoritative structured consequence source for event options. Rendered
text is public evidence that a policy may interpret; it is not a parsed effect
program, a safety proof, or a promise about the next screen.

The first implementation slice should remain deliberately asymmetric:

- changed visible option projections and an explicitly completed child may
  create a new event step;
- an unchanged projection after an accepted action remains non-actionable
  waiting;
- an allowlisted typed item child is delegated to the future loot controller;
- visible embedded combat becomes a typed combat-child handoff rather than
  proof that the event parent is complete; and
- map completion remains unavailable until static source evidence identifies a
  public event-exit fact that distinguishes an event exit from map inspection.

That last limit is mandatory. Merely seeing an open, travel-ready map is the
exact inference D47 currently withholds.

## 2. Current source-backed inventory

### 2.1 Public event option fields

The current reader and wire expose the following exact event-option surface.
Sources are
[`PinnedPublicRoomDecisionReader.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRoomDecisionReader.cs),
[`PublicRoomDecision.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Public/PublicRoomDecision.cs),
[`CanonicalProbeEncoder.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Core/Protocol/CanonicalProbeEncoder.cs),
and the strict host parser in
[`apply_room_live.py`](../../bridge/Sts2AgentBridge/tools/apply_room_live.py).

| Wire field | Current producer fact | What it does **not** establish |
| --- | --- | --- |
| `candidate_index` | Zero-based position in the currently enumerated visible event buttons, bounded to at most eight candidates. | Durable option identity across a changed step. |
| `action_id` | `choose:<candidate_index>`. | Semantic meaning or effect. |
| `kind` | Always `event_option` for standard-event buttons. | Finality, exit, child type, or value. |
| `stable_id` | `EventOption.TextKey`, required to be nonempty printable ASCII and at most 96 characters. | Rendered localized prose, structured cost, structured effect, or a globally stable content ID. |
| `enabled` | Button visible and enabled, option unlocked, and current `is_dangerous=false`. | Desirability, affordability beyond the UI state, or supported continuation. |
| `supported` | Exactly the inverse of `is_dangerous` for event candidates. | That the consequence or next screen is implemented. |
| `is_proceed` | Always `false` for event candidates. A visually final event option remains indexed. | Whether selecting it exits the event. |
| `is_dangerous` | Result of the option's `WillKillPlayer` predicate. A missing predicate is non-dangerous; a predicate with unavailable event owner fails dangerous. | Any nonlethal HP loss, gold/card/relic/potion cost, downside, probability, future combat, or strategic value. |

A ready room decision additionally exposes `decision_id`, `screen_kind=event`,
`phase=choose_option`, `room_ordinal`, the ordered candidates, and the complete
set of enabled/supported legal actions. The decision hash binds the room
ordinal, candidate order, IDs, keys, and flags. It has no event-step component.
The checked-in strict DTO parser
[`game/backends/live/r0i_wire.py`](../../game/backends/live/r0i_wire.py)
accepts exactly this shape and is bound to bridge `0.8.0`, `live_probe_v0`, and
the current vector inventory.

### 2.2 Why `safe` means first eligible non-lethal

The host selector in
[`apply_room_live.py`](../../bridge/Sts2AgentBridge/tools/apply_room_live.py)
walks candidates in producer order and returns the first candidate that:

- is an `event_option`;
- has `is_dangerous=false`; and
- has an action ID present in `legal_actions`.

It does not inspect `stable_id`, option text, player state, costs, effects,
probabilities, or future screens. The C# applier rechecks visibility, enabled
state, lock state, the same `TextKey`, and `WillKillPlayer`, then reserves the
decision before clicking. Therefore `safe` currently means **first advertised
eligible option not known by the one immediate-lethal predicate to kill the
player**. It is not effect planning, consequence validation, or value ranking.

The name must keep that narrow interpretation unless a separately reviewed
provider consumes a richer public observation. Existing provider behavior is a
compatibility default and should not silently change when rendered text is
added.

### 2.3 Current action and receipt boundary

[`PinnedPublicRoomActionApplier.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRoomActionApplier.cs)
provides these protections:

- the current full decision and room instance are revalidated immediately
  before reservation and click;
- one accepted action is reserved per decision ID;
- stale or invalid input does not consume the 12-action process budget;
- a reserved decision cannot be used again; and
- reservation occurs before click, so an exception or lost response after
  reservation stays uncertain and cannot be retried.

An exact accepted receipt is recorded by the Python controller only after the
strict receipt body matches the submitted decision/action pair. It still does
not reconcile the option's effect. D49's distinction applies unchanged:
attempt, accepted/bound receipt, and reconciled transition are separate facts.

### 2.4 Current parent lifecycle

The current lifecycle in
[`PinnedPublicRoomDecisionReader.cs`](../../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRoomDecisionReader.cs)
has a stable bounded registry of numeric run/room pairs and volatile evidence
for the most recent ready/accepted decision.

- A missing run/room, traveling state, or foreground map clears volatile
  evidence and yields `waiting`.
- Any nonempty overlay stack, simultaneous visible rest/event rooms, or custom
  event node yields `unsupported` before standard-event projection.
- An unchanged projection after an accepted action yields `waiting`.
- A changed projection becomes ready, but A -> B -> A recreates A's old hash;
  the intact reservation correctly rejects it as already applied.
- Visible `EmbeddedCombatRoom` can yield `complete` only while an accepted
  same-event pending decision still exists.
- Event-to-map completion is deliberately unavailable.

D47 and the production-backed event study record these behaviors in
[`DECISIONS.md`](../../DECISIONS.md#d47-separate-room-identity-from-foreground-and-completion-evidence)
and
[`PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md`](PHASE_1_NEXT_INCREMENT_ACCEPTANCE.md#event-investigation).
The latest sanitized campaign established one ready event action exchange and
accepted receipt followed by `unsupported`; it did not identify the selected
option, effect, payload, or unsupported cause. See
[`PHASE_1_ACTOR_READY_ACCEPTANCE.md`](PHASE_1_ACTOR_READY_ACCEPTANCE.md#2026-09-05--targeted-event-diagnostic-observed-unsupported-continuation).

## 3. Facts, hypotheses, and precise unknowns

### Repository facts

- `TextKey`, `IsLocked`, and `WillKillPlayer` are the only event-option members
  in the current production allowlist.
- `NEventLayout.OptionButtons`, `NEventOptionButton.Option`, and
  `NEventOptionButton.Event` are allowed and used.
- `NOverlayStack.ScreenCount` and `Peek()` are allowlisted, but production uses
  only the count for the generic room guard.
- `NEventRoom.Layout`, `CustomEventNode`, and `EmbeddedCombatRoom` are
  allowlisted.
- The maximum response body is 4096 bytes; current JSON is strict ASCII.
- Current strict parsers, golden vectors, package identity, and public-surface
  allowlist are exact-contract artifacts, not flexible readers.
- The offline common-subset comparator explicitly omits room effect amounts,
  effect kinds, option identity, and player vitals; structural headless event
  rules are not target-game truth.

### Hypotheses, not accepted facts

- The visible loot screen after the last accepted event receipt may have been
  the nested overlay that triggered `unsupported`.
- A visible event button or its child controls may expose already-rendered
  localized text through a safe public property.
- A layout object, event model, or room signal may expose a reliable logical
  step or exit marker.
- `NOverlayStack.Peek()` may permit a narrow type classification for an item
  child without reading item contents through the event reader.

None of these hypotheses may enter production or a fixture as assumed target
behavior.

### Missing static facts required before production

The first later packet must establish, from the pinned target API and method
surface without live execution:

1. the exact member path that returns the text currently rendered for one
   visible `NEventOptionButton`, including whether it is plain text, localized
   text, rich text, or a key;
2. whether reading that value invokes localization or game mutation, and what
   encoding/control characters and maximum observed representation it permits;
3. the exact public type/member that distinguishes an item-reward child from
   every other overlay, and whether it can be bound to the current event parent
   rather than merely being globally foreground;
4. the exact fact, if any, that distinguishes event exit to map from inspection
   map opening and binds the exit to the accepted current-event action;
5. the exact fact, if any, that distinguishes a new logical event step when the
   rendered candidate projection is unchanged; and
6. after an embedded combat or item child resolves, whether the same
   `NEventRoom` resumes, is replaced, disappears, or exposes an explicit parent
   continuation signal.

If a fact is absent, the corresponding branch stays waiting or unsupported.
Do not substitute engine instance IDs, object disappearance, a changed overlay
count, or a guessed content key for public transition evidence.

## 4. Proposed public option observation

This section is a contract candidate for coordinator review, not a freeze.

### 4.1 Add only rendered public text

For each `event_option`, add one required field in a successor protocol:

```json
"rendered_text": "<exact player-visible option text>"
```

Proposed constraints:

- source only the already-rendered value of the current visible button;
- encode as UTF-8 JSON without Unicode normalization or semantic parsing;
- reject NUL and non-display control characters; preserve visible line breaks;
- cap each value at 256 UTF-8 bytes and retain the existing eight-candidate and
  4096-byte response limits;
- never truncate; an unavailable, malformed, or over-limit value makes that
  event projection `unsupported`; and
- include `rendered_text` in decision identity and immediate revalidation.

The 256-byte bound is a proposed engineering bound chosen to preserve the
existing total response ceiling. The static discovery packet must confirm it
is usable for the pinned surface; otherwise the coordinator must revise the
bound and response/version contract before implementation.

`stable_id` remains the bounded `TextKey`; it is not renamed or presented as
rendered prose. No `cost`, `effects`, `probability`, `outcome`, `value`,
`exit`, or `child_kind` is inferred from either text field.

### 4.2 Why structured costs/effects are deferred

Parsing rendered text would duplicate game semantics, depend on locale and
formatting, and turn presentation strings into an authority they do not have.
`WillKillPlayer` is too narrow to fill that gap. Structured costs/effects may
be added only after a separate source audit identifies authoritative public
members and differential fixtures show that their order and conditions match
the rendered UI on the pinned build.

The default `safe` provider remains unchanged. A later text-aware or
effect-aware provider must have a new explicit name and separate acceptance;
it must not be smuggled into this observation change.

## 5. Proposed event-parent lifecycle

### 5.1 Parent and step identity

Keep the current run/room registry and add an event-local monotonic
`event_step_ordinal`, bounded to the existing 12 accepted room actions. The
ordinal is operational lifecycle state; whether it appears on the wire is a
shared coordinator decision. It must be included in the successor event
decision identity so A -> B -> A cannot collide with the original A.

The ordinal may advance only from public history after the current step has an
exact accepted/bound receipt:

- two consecutive validated reads of a different current option projection;
  or
- exact completion of an allowlisted child followed by two consecutive
  validated reads of the same bound parent event, even if its visible options
  equal the pre-child projection.

The two-read rule is proposed to prevent a one-read animation/reorder race from
minting a step. Both reads must agree on parent identity, ordered candidate
keys/text/flags, legal actions, and foreground classification. No action occurs
between them.

An accepted action followed by an unchanged projection remains
`accepted_waiting`; it does not create a new decision. This deliberately leaves
identical no-child consecutive steps unsupported unless the missing static fact
in Section 3 supplies an authoritative step marker.

### 5.2 State machine

| Parent state | Public behavior | Allowed transition evidence |
| --- | --- | --- |
| `ready(step)` | Advertise the current event candidates once. | Exact current decision. |
| `accepted_waiting(step)` | No candidates; no retry. | Exact accepted/bound receipt for that step. |
| `child_handoff(step, kind)` | No event candidate; route one typed child. | Same parent, accepted step, and allowlisted foreground child classification. |
| `child_active(step, kind)` | Parent remains suspended. | Child controller owns its own observations/actions/receipts. |
| `resume_pending(step)` | No candidate while parent is revalidated twice. | Exact child completion plus same bound parent visibility. |
| `ready(step+1)` | Fresh identity even if visible options repeat. | Stable changed projection or completed-child resume. |
| `exit_pending(step)` | No candidate. | Accepted step plus authoritative event-exit evidence. |
| `map_handoff` | Parent may be called complete; map owns the next decision. | Bound exit evidence **and** fresh actionable/travel-ready map, not map visibility alone. |
| `combat_handoff` | Parent suspended; existing combat controller owns the child. | Accepted same-event step and visible bound `EmbeddedCombatRoom`. |
| `unsupported` | Stop immediately. | Unknown/custom/nested/racy/malformed state or exhausted bound. |

Disappearance does not reset the parent or any reservation. A changed run,
room, immutable kind, or exhausted 1,000-identity registry fails closed as it
does under D47.

### 5.3 Typed child handoff

The event lane should consume, not define, a shared handoff envelope. The
coordinator-owned contract must at minimum bind:

- parent family `event`, parent room ordinal, and parent step ordinal;
- the accepted parent decision/action accounting record;
- one child kind, initially `item_reward` or `combat`;
- one non-action handoff identity/lifetime; and
- a return disposition of `resumed_parent`, `parent_exit_pending`, or
  `unsupported`.

For `item_reward`, `MR-LOOT-02` exclusively owns observation, collection,
replacement, decline/skip legality, receipts, completion, and inventory
reconciliation. The event controller only suspends the parent, invokes that
reviewed interface, and revalidates the parent afterward.

For `combat`, use the existing combat client after a typed handoff. Combat
victory or defeat resolves the child only. Victory does not prove the event
completed; defeat may terminate the run under existing combat truth. After
victory, the event parent must be observed again for resumed choices or a
separately proved exit.

Child completion can justify a resume boundary; it cannot by itself prove
parent completion. A child appearing without an accepted bound parent action,
or with an unknown parent, is unsupported and never adopted.

### 5.4 Receipt and action accounting

- Count the parent option once, when its exact accepted/bound receipt is
  validated.
- A handoff, poll, stable-read confirmation, resume, or completion marker is
  not an action.
- Count child actions only in the child controller's own category and aggregate
  them once at the shared runner boundary.
- A rejected or stale receipt counts no accepted action.
- A duplicate receipt/request never increments either count.
- A lost, malformed, unbound, or transport-uncertain receipt stops the whole
  continuation. Preserve the reservation and make no retry or child adoption.
- An accepted receipt is not effect reconciliation. A later child, choice, or
  exit is transition evidence only; it does not prove the advertised prose's
  consequence occurred exactly.
- No parent or child action can be moved between categories merely to make the
  existing total reconcile.

## 6. Proposed protocol and compatibility impact

This work cannot be shipped as an unnoticed `live_probe_v0` body change.
Adding `rendered_text`, event-step identity, or a typed handoff changes exact
canonical JSON, hashes, vectors, strict parsers, and artifact identity.

The coordinator should choose one explicit successor binding (for example a
new protocol/schema and bridge minor version) while preserving bridge `0.8.0`,
`live_probe_v0`, D47, and existing defaults as an immutable compatibility path.
No consumer should accept both shapes heuristically.

Proposed future ownership after contract freeze:

| Boundary | Likely owned files | Impact |
| --- | --- | --- |
| C# public model/identity | `Core/Public/PublicRoomDecision.cs`; possibly a new event lifecycle type | Event text, step, handoff representation; decision hash change. |
| C# producer/lifecycle | `Adapters/Public/PinnedPublicRoomDecisionReader.cs` | Rendered-text read, stable-step state, typed child/exit classification. |
| C# action revalidation | `Adapters/Public/PinnedPublicRoomActionApplier.cs` | Revalidate text/step/parent and preserve reservation-before-click. |
| Canonical wire | `Core/Protocol/CanonicalProbeEncoder.cs`, `LiveProbeLimits.cs`, successor vectors/contracts | UTF-8 canonicalization, exact fields/statuses, bounds. |
| Surface verifier/package | `forbidden_surface.json`, project file if new sources, verifier fixtures, package/version manifests | Every newly read target member must be allowlisted and artifact-pinned. |
| C# tests | `RoomInteractionTestSuite.cs`, contract/transport suites | Lifecycle, hash, malformed, race, cap, and child cases. |
| Host room client | `tools/apply_room_live.py` and its fixture suites | Strict successor parser, unchanged default `safe`, parent state loop. |
| Run routing/accounting | `tools/apply_run_live.py`, acceptance/diagnostic validators and actual-client fixtures | Typed child dispatch, post-child parent revalidation, once-only totals. |
| Strict live DTO | `game/backends/live/r0i_wire.py`, its tests, accepted vector inventory | New explicitly versioned parser; do not mutate `r0i_wire_v0` in place. |
| Differential common subset | `tests/differential/common_public_subset.py`, synthetic cases and identities | Rendered text remains omitted unless a reviewed headless correspondence exists; no synthetic effect promotion. |
| Shared docs/decisions | bridge README, current status, execution ledger, DECISIONS, roadmap if selected | Coordinator-only consolidated update after acceptance. |

`headless_v0`, `headless_encoding_v1`, legacy combat encoding, model
fingerprints, training artifacts, and D47 remain unchanged unless a later
separate contract explicitly versions them. Rendered event prose must not be
silently fed into an accepted actor encoder.

Rollback is simple until live acceptance: keep the successor disabled/unselected
and use the exact current bridge/protocol/provider path. Any unexpected child,
missing text, unstable step, exit ambiguity, parser mismatch, cap exhaustion,
or receipt uncertainty fails closed without falling back to `live_probe_v0`
mid-interaction.

## 7. Synthetic acceptance specification

The following is a specification for future independently authored fixtures.
It is not passing runtime, target-game, or live evidence.

| ID | Case | Required result |
| --- | --- | --- |
| E01 | Passive ready read with two visible standard-event buttons. | Exact key, rendered text, flags, order, legal actions, parent/step; zero click, reservation, or action count. |
| E02 | Repeat the same passive read. | Byte-identical canonical body and identity; no lifecycle advancement. |
| E03 | First button lethal/locked/disabled, second eligible. | Existing `safe` selects the second indexed action; no text/value interpretation. |
| E04 | Nonlethal but harmful-looking rendered text. | Candidate may remain legal under current safety rule; fixture explicitly proves no value/effect claim. |
| E05 | Accepted A, stable B, accepted B, stable A. | Step ordinals and IDs are A0/B1/A2; old A0 remains already applied; only A2 may apply. |
| E06 | Accepted A followed by unchanged A until deadline. | `accepted_waiting`; no second POST, no new ID, no inferred completion. |
| E07 | Accepted A followed by one transient B read then A. | Two-read gate does not mint B; stays waiting. |
| E08 | Accepted A followed by stable reordered/changed candidates. | New step only after two matching reads; old action is stale; revalidation uses exact new order/text/flags. |
| E09 | Candidate text/key/enabled/danger changes between selection and dispatch. | Immediate revalidation rejects stale; no click or budget consumption. |
| E10 | Foreground map or traveling state appears before dispatch. | Stale/no click; no event completion. |
| E11 | Unsupported overlay appears before dispatch. | Stale/no click; later observation unsupported; reservation behavior remains exact. |
| E12 | Allowlisted item child appears after accepted/bound parent action. | One typed handoff, no additional event POST, parent suspended; item semantics delegated. |
| E13 | Item child appears without accepted parent action or for another parent. | Unsupported; no child adoption or action. |
| E14 | Item child completes and identical parent choices return. | Child completion alone is not parent completion; two stable same-parent reads create the next step. |
| E15 | Item child completion is followed by a map with no authoritative event-exit fact. | Remain waiting/unsupported; never report event complete. |
| E16 | Visible bound embedded combat after accepted event action. | Typed combat handoff; no event completion and no double-counted handoff action. |
| E17 | Embedded combat without accepted same-event action. | Unsupported/waiting under the frozen rule; do not adopt combat as this parent. |
| E18 | Combat child wins and parent resumes choices. | Combat counts once in combat; event action once in room/event; parent produces a fresh step only after revalidation. |
| E19 | Combat child resolves then map appears. | Combat resolution does not prove event completion; require separate bound exit evidence. |
| E20 | Accepted exit action plus authoritative same-parent exit fact plus fresh travel-ready map. | Exactly one `map_handoff`; parent complete only after both facts; no extra action count. |
| E21 | Inspection map opens/closes before or after a non-exit action. | Never completes parent; replay reservation survives. |
| E22 | Rejected stale/invalid/action-limit/already-applied receipt. | Stop with exact reason; no accepted count, child handoff, or retry. |
| E23 | Exact accepted receipt arrives twice. | Parent accepted count remains one; second request/receipt is duplicate evidence only. |
| E24 | Transport fails before delivery. | Attempt may increment diagnostic attempt count; accepted count stays zero; all continuation stops. |
| E25 | Click/reservation may have happened but receipt is lost, malformed, or unbound. | Mutation is uncertain; reservation retained; no retry, child adoption, or completion inference. |
| E26 | Accepted receipt followed by changed public state. | Receipt and transition are recorded separately; no structured effect assertion. |
| E27 | Empty, invalid, non-display-control, over-256-byte, or unreadable rendered text. | Projection unsupported; no truncation, key fallback, or action. |
| E28 | Non-ASCII rendered text at/under the byte bound. | Canonical UTF-8 round trip and hash stability; ASCII key remains unchanged. |
| E29 | Duplicate/missing/unknown JSON fields, invalid UTF-8, noncanonical order, or mismatched step/handoff linkage. | Strict parser/encoder rejection; no action. |
| E30 | More than eight candidates, 13th accepted room action, new 1,001st identity, or response over 4096 bytes. | Existing applicable bound fails closed; known retained identities remain valid for replay rejection. |
| E31 | Parent disappears and returns; A -> B -> A; run/room/kind changes. | Disappearance never resets reservation; same parent uses monotonic step; replacement/kind conflict is stale or unsupported. |
| E32 | Child controller rejects, times out, is cancelled, or has uncertain receipt. | Whole interaction stops; parent is not resumed automatically; no later POST. |
| E33 | Child completes but parent validation fails or another parent appears. | Child result cannot complete or transfer to the wrong parent; stop before event/map action. |
| E34 | Full event -> item child -> resumed event -> combat child -> resumed event -> explicit map exit. | Exact request order; each accepted parent/child action counted once; handoffs counted zero; no phase scan or fallback. |
| E35 | Cancellation or exception at every read, parse, receipt, handoff, and resume boundary. | Sockets close; mutable request/response/credential buffers are zeroed; fixed sanitized output only. |
| E36 | Secret/canary in target exception, text source, malformed child, or transport buffer. | No canary/raw body/engine identity appears in output, diagnostics, or fixture artifacts. |
| E37 | Process/controller restart after accepted or uncertain action. | No transparent recovery, journal adoption, or retry; explicit fresh entry remains required. |
| E38 | Existing `live_probe_v0`/0.8.0 vectors and default room/run fixtures. | Remain byte- and behavior-exact on the compatibility path. |

Independent review must include a negative control that applies the successor
transcript to the exact current production source and observes its intended
fail-closed/unsupported behavior. Fixture authors must use actual producer and
consumer entry points with literal synthetic transport rather than reproduce
the lifecycle in a second model.

## 8. Dependency-ordered implementation plan

1. **Static source packet (read-only).** Establish the six facts in Section 3,
   enumerate exact target members/types and passivity, and return a minimized
   member-use proposal. If rendered text, item-child classification, or exit
   evidence is absent, mark only that branch unavailable.
2. **Coordinator contract freeze.** Reconcile this proposal with
   `MR-LOOT-02` and `MR-SHOP-01`; choose shared lineage, handoff, uncertainty,
   accounting, status, version, and artifact semantics. Record an exact hash
   before production or consumer fixtures encode the result.
3. **Observation producer.** Add bounded rendered text and event-step identity
   behind the successor contract. Preserve current protocol/version unchanged.
4. **Independent observation gate.** Verify strict UTF-8/bounds, passive reads,
   public-information scope, hash stability, immediate revalidation, malformed
   input, and compatibility negative control.
5. **Parent lifecycle producer.** Implement accepted waiting, changed-step
   continuation, typed combat handoff, and the reviewed item-child interface.
   Implement map exit only if the static fact was accepted.
6. **Independent lifecycle/actual-client gate.** Exercise E05-E38 through real
   entry points and synthetic sockets, including deliberate producer mutants
   for double accounting, child-equals-parent-completion, map-inspection
   inference, receipt retry, and cleanup leaks.
7. **Integration review.** Inspect complete diffs and artifact surface; run all
   current room/run/transport/vector/parser/differential gates plus successor
   gates and the full repository suite. Update shared docs once, coordinator-
   owned.
8. **Fresh bounded live gate, separately authorized.** Run only after source,
   artifact, fixture, independent review, package, and cleanup gates pass. One
   invocation, capture-off, no retry, and no retained raw payload.

### Smallest useful first slice

If static discovery finds rendered text and a typed item-child classifier but
no event-exit marker, implement only:

> bounded rendered option text + step ordinal for changed/resumed projections
> + one item-child handoff/resume + existing embedded-combat handoff, with
> event-to-map still fail-closed.

This slice addresses the observed class of unsupported child surface without
inventing parent completion. If the item classifier is absent, reduce further
to rendered text plus changed-projection A -> B -> A continuation; do not
pretend that generic overlay suppression is item support.

## 9. Fresh UI state for a later live test

The first observation-only test needs this exact visible boundary:

- dedicated Profile 3, Ironclad, Ascension 0;
- the pinned supported build and reviewed successor bridge only;
- one fresh **standard** question-mark event, not a custom event;
- the event body and option buttons fully visible, with no map or overlay open;
- every option untouched and no prior controller action in that event; and
- no resumed or uncertain earlier room action.

The first child-continuation test additionally requires a coordinator-selected
standard event whose specific currently visible eligible option is established
by the accepted static packet to open the one reviewed `item_reward` child.
The parent options must be visible and untouched at invocation; the controller,
not the user, selects the option. The resulting child must also remain untouched
for the loot controller. No repository evidence currently identifies a safe
event/option name that satisfies this requirement, so naming one now would be
invented. That exact content selection is a prerequisite for the later live
request, not permission to explore routes or repeat events until one appears.

An event-to-map live acceptance additionally requires the accepted static exit
fact. Without it, a visible map can be recorded only as an unaccepted
transition observation and the controller must stop.

## 10. Exclusions and evidence disposition

This proposal does not include:

- item collection, replacement, decline, skip, inventory, or potion-use rules;
- shops, treasure, boss/act transitions, rest upgrade submodals, nested combat
  choices, card-reward redesign, or generic modal refactoring;
- structured event effect extraction, text parsing, consequence simulation,
  provider value ranking, or a claim that nonlethal means beneficial;
- automatic phase detection, crash recovery, journals, uncertain-action
  adoption, retries, or fallback to another protocol;
- production, test, wire, vector, package, export, dependency, headless,
  encoding, model, or shared-document changes; or
- any game launch, UI operation, install/build against the game, endpoint,
  credential, profile/save filesystem, Steam Cloud, retained live data, remote
  Git, or discarded-response reconstruction.

The acceptance matrix is design evidence only. Until the coordinator freezes a
successor and its producer/gates pass, bridge `0.8.0`, `live_probe_v0`,
`headless_v0`, D47, current completion behavior, and all accepted defaults
remain exact.
