# Generic event v3 — reward-card additions

2026-09-07. Accepted functional contract for a successor to frozen generic_event_v2. Preserve all sixteen
predecessors, their identities/contracts and the original bridge. Retain shared
upgrade-one and removal1..8, adding standard reward-card offers with exact selected-
original addition. Event names remain tests and ownership, never semantic rows.

## Authoritative reward admission

Observe exactly two additional public methods under the existing owner-thread
Chosen/request scope: CardSelectCmd.FromSimpleGridForRewards(PlayerChoiceContext,
List<CardCreationResult>,Player,CardSelectorPrefs) and the
NSimpleCardSelectScreen.Create(IReadOnlyList<CardCreationResult>,CardSelectorPrefs)
overload. Preserve the five v2 hooks. Originals always run; no argument/result
replacement, transpiler, private-field access or event-name rule. Distinguish the
CardCreationResult overload from plain CardModel grids and reject mixed requests.

Reserve exact event/controller/run/player/room/map/IRunState and complete deck
before parent dispatch. At the owned reward request capture a nonnull opaque
PlayerChoiceContext, exact explicit Player, exact List identity, unique result-entry
references, their effective public Card references/keys/upgrade levels and all prefs.
The context has no assumed Owner property; explicit Player and scoped invocation
establish ownership. Each result Card must be unique, owned by the reserved player,
in the exact run state and absent from the complete baseline deck. Require domain
max < count <=64 and baselineCount+max<=512. These are off-deck offer originals;
no global novelty or specific generation algorithm is claimed.

Require the same request List/entry/Card projection and preferences at the owned
Create entry and returned-screen binding; recheck full reserved context and entire
unchanged baseline deck. Recheck the retained offer projection during child control.
Native Create may sort a copy via Comparison, so holder slots form an exact
bijection to offer originals; do not require click/slot order to equal request
order. A changed result.Card, replaced entry, duplicate, preexisting deck card,
wrong player/context, replaced screen, second request or selectorless shortcut stops.
Synchronous setup is buffered until request/Chosen Tasks are captured; delayed setup
must preserve exact asynchronous ownership. Keep lifetime task/screen tombstones.

This expressly extends two-stage admission to reward offers: the predispatch
reservation does not predict generation inputs/counts. Authoritative request
arguments establish the offer before child actions. It does not retroactively
change frozen predecessor generation-before-dispatch contracts.

## Modes and completion

Use new GenericEventV3 types, generic_event_v3 outer protocol/routes and host.
Keep the frozen card_selection_v1 payload and actual CardSelectionV1Session.
Publish the existing immutable opaque admission with operation add, authoritative
1<=min<=max<=8, domain count and one of two modes:

- RequireManualConfirmation=false: auto_at_max. The final select at exactly max
  submits natively; no preview or confirm action/receipt is allowed. Min remains
  authoritative metadata, but this mode has no early-commit control.
- RequireManualConfirmation=true: explicit_confirm. Native Confirm in selecting
  is available from min through max; max does not auto-submit. No preview exists.

Cancelable or zero-count offers remain unsupported. Upgrade/removal keep their
v2 preview_confirm semantics unchanged. Bind exact native grid/controls, complete
visible geometry and original references; verify candidate identity/key/level and
selected membership before every mutation. Never synthesize a selection or replace
native UI execution. After the final auto select, task originals can reconcile
selection even when the screen has already closed.

The reward command returns selections; it does not itself promise a deck mutation.
This supported family requires add-only completion by the owned parent callback.
Snapshot request and selector results once within max+1, rejecting duplicates,
foreign or missing originals. Both must equal the exact selected-original set;
request and awaited Chosen Tasks must succeed, and the selector must close.
The frozen card core then proves that all selected exact originals were added,
all baseline originals retain order/key/level and no extra deck delta occurred.
Partial additions may progress monotonically while tasks are pending. Replacement
cards, unselected additions, reorders/upgrades/removals of baseline cards, revoked
progress, no additions or faults never yield successful add completion. Other HP/
gold effects remain uncertified. No separate CardPileCmd.Add task, completion
of all add hooks/animations, or global event-state postcondition is certified. Failures retain attempts and accepted receipts,
report unverified effects and never retry uncertain actions.

## Host, wire and validation

Retain12 parent actions,4 children,52 total actions,10 per child,2048 reads and
one30-second host deadline. Retain deeply immutable providers, opaque native
admissions, exact descriptor/lineage and ordered receipt histories. Selection
membership is a duplicate-free set independent of receipt and native slot order.
Validate legal actions before publication: select only eligible unselected slots
below max; explicit Confirm only at legal count; auto mode only selects; preview
modes preserve their exact preview witness and final Confirm requirement.

Resolved auto children must follow exactly max accepted selects, ending in select,
with selected history rows and no committed row. Explicit children require final
Confirm and its committed history row at min..max; neither needs preview_seen.
Reject mode/count/operation changes, early auto completion, extra terminal controls
and mismatched selected results before further dispatch.

Required evidence preserves all v2 cases and adds unrelated/held-out event reward
fixtures through actual hooks/native/card/core/wire/Python; fixed and variable
limits in both modes, reverse click order and sorted offers, max8/domain9, delayed
creation/partial additions/completion, mixed upgrade/remove/add child episodes,
mutated offer/result references, wrong owner/context, preexisting deck originals,
wrong task sets, early/extra/wrong deck effects and lost final auto-select/Confirm
responses without retry. Compile against pinned target references without execution
and compare two native builds in disposable snapshots. No new target inspection
is needed when retained source hashes verify the request/screen APIs.

Root owns contract/core/wire/checker/provenance/docs. Native lane owns native/
(except derivation.json), native_tests/ and retained-evidence summary after review.
Host/review lane owns host/host_tests/ and independent source review. Integration
lane owns wire_tests/, integration/ and integration_tests/. One SDK lane at a time.
Freeze only after review, all integrated tests and whitespace checks pass, then
repeat the aggregate against the frozen identity. No package, listener, install or
live claim; real EventSynchronizer context preservation remains a live gate.

Independent design review accepted this contract, including variable auto-mode
limits, retained baseline disjointness during insertion, and the explicit bounded
card-effect claim. No new target inspection is needed for the retained APIs.
