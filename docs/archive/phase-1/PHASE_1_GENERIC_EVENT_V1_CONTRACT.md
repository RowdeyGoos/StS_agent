# Generic event v1 — two-stage functional contract

2026-09-06. Successor to the frozen event-card operations component. This
contract selects a standard upgrade interaction vertical slice, without event
name/key registration. All fourteen accepted successors and original48 remain
unchanged. Functional validation, patch-engine validation, target compilation,
release and live acceptance are separate evidence levels.

## Authoritative boundary

The new integration observes exactly three public calls: EventOption.Chosen(),
CardSelectCmd.FromDeckForUpgrade(Player, CardSelectorPrefs), and
NDeckUpgradeSelectScreen.ShowScreen(IReadOnlyList<CardModel>, CardSelectorPrefs,
IRunState). Their retained pinned metadata/IL identifies the first call's returned
Task as the awaited option completion, the second as the upgrade-family selection
request, and the third as the actual complete candidate/prefs creation boundary.
No private fields, option-text rule inference or event-type allowlist is used.

Narrow Harmony prefix/postfix/finalizer instrumentation is selected for this new
component only. No transpiler, argument/result replacement, skipped original,
private field access or permanent game-file patch is selected. All hooks require
an active reserved bridge-owned event action and retain reference identity.
Installation must reject existing foreign patches on the three methods, use one
exclusive owner, roll back partial installation and unpatch only its own hooks.
This is a new dependency/instrumentation boundary, never part of an old release.
Pure tests must patch inert stubs using the real engine; the game is compile-only.

## Two-stage admission and ownership

Before dispatch reserve the exact run/player/room/map/event/option/controller,
exact IRunState, complete deck (max512 originals, keys and levels), action receipt identity and
baseline public counters. The ordinary parent does not promise a card operation
or counts before the choice. It explicitly advertises deferred discovery.
Arm instrumentation before the one native option dispatch. Bind Chosen's Task
and an AsyncLocal invocation scope; restore the caller scope even on throw.
A deferred callback inherits its own closed-over invocation, not any newer action.

The upgrade command captures prefs and player under that invocation; the actual
ShowScreen captures ordered originals, prefs and run-state and binds its returned
screen once. Require consistent prefs, exact player/context and a complete1..64
unique domain contained in the pre-action deck with unchanged original levels.
The entire pre-action deck (order, original references, keys and levels) must
remain unchanged at admission. No startup/replacement/preselected/completed selector is admitted. Reject a second
command/screen, cancellation, nested or foreign choice, lost context, mismatch,
unsupported mode or post-closure callback. Never reopen a receipt's child window.
Screen and task identities remain lifetime tombstones. Synchronous creation is
buffered until both returned request/Chosen tasks are bound. Any observed upgrade
request that auto-shortcuts or never creates the owned screen terminalizes
unsupported; it cannot become an ordinary no-child transition.

The first supported mode is exactly one upgrade with native preview confirmation,
noncancelable and at least two eligible candidates (avoid native auto-shortcut).
Both RequireManualConfirmation preference values are captured and matched exactly;
the screen requires the native preview confirmation regardless of this value.
The standard one-card preview publicly exposes its original. Multi-upgrade,
optional selection, add/remove/transform, repeated-key choices, scrolling, custom
screens and event combat stop explicitly until their shared boundaries are
implemented and validated; they are not admitted using event names.

Instantiate the actual frozen CardSelectionV1Session for the child. Its native
adapter uses the creation originals and original-card preview; complete deck,
layout, holder/card/reference identity and enabled native controls are recaptured
before every mutation. Its effect-completion witness requires both selection-task
success and the exact Chosen Task success, selector removal and exact upgrade
delta; no finished-flag-only or apparent-delta-only completion.

Parent callback effects before child creation are possible. A failure after parent
dispatch must retain attempted/accepted action accounting and report effects as
unverified when the complete callback/effect witness is absent. Never report zero
effects, undo, retry or resume after uncertain mutation. A successful child means
its exact card effect only, not certification of other HP/gold consequences.

## Parent, wire and host

Preserve bounded ordinary event option pages and explicit Proceed/map handoff,
context recapture, stable-key replay exclusion, one active child and reserved
receipts. Use a distinct generic_event_v1 outer envelope/decision/action route;
frozen card payload semantics remain unchanged. Parent has12 actions, at most4
children,52 total actions,2048 reads and one30-second monotonic host deadline.
Child action messages carry the exact parent receipt and child ordinal; clients
cannot supply descriptors, operation, counts or native identities. Public admitted
metadata exposes operation/count/mode/domain from the owned creation receipt.

The Python decision provider consumes deeply immutable public observations and
returns one advertised legal action. Validate once per decision, correlate exact
receipts, preserve counters on errors and stop after uncertain POST or late return.
Unknown keys, wrong lineage, descriptor changes and unsupported modes reject.

## Acceptance and ownership

Root owns this contract, wire/host, integration and checker/documentation.
Native lane owns core/native and native tests only after independent contract
review. Review lane owns read-only review initially, then independent fixtures
under its exclusive test paths. No writes to frozen predecessors.

Required tests: real production hooks against inert game stubs, actual frozen
card session and C# to Python flow; two unrelated event identities and one held-out
identity with no catalog entry; synchronous and asynchronous creation, before-child
effects, wrong player/event/option, stale invocation, task/screen substitution,
second request, canceled/faulted callback, early matching delta, stale actions,
preview confirmation, ordinary pages and explicit Proceed/map, unsupported count
and operation, exhausted budgets and one dispatch after uncertain result.
Compile-only pinned target checks never execute the game. No package/install/live
claim is made without the separate release gates.

## Independent design review

The independent contract reviewer accepted this boundary subject to the six
clarifications now incorporated above: request-task equality, preview preference
semantics, reserved run-state, whole-deck admission, selectorless-request rejection
and buffered asynchronous ownership. Root accepts this contract for functional
implementation. Real Harmony2.4.2 inert prefix/unpatch smoke passed on the local
SDK9.0.303; the target game was not loaded. Dependency package SHA-256:
`d64592e53090464559fce48612c9ca7c8dc73113841376b7aa3455f46fc5d579`.
