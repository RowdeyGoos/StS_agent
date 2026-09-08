# Generic event lifecycle v1 contract

2026-09-07. Native lifecycle correction following the first generic release's
accepted Gorge dispatch and unsupported second read. The user asked to proceed
with diagnosis and correction. No campaign is active; keep the game closed.

## Evidence and scope

Retained pinned metadata establishes that non-shared ordinary event dispatch
calls NEventLayout.ClearOptions before EventSynchronizer. ClearOptions removes
and queues option buttons for freeing. The frozen v3 binding incorrectly requires
the original button to remain a valid Godot object throughout the interaction;
its three child adapters also dereference that button after dispatch. This is a
concrete lifecycle mismatch, consistent with but not proven to be the sole cause
of the live failure. Real EventSynchronizer ExecutionContext preservation remains
unproven. Never substitute a global armed binding when scoped causality is lost.

New component: successors/generic_event_lifecycle_v1. Preserve all eighteen frozen
components/contracts and the original bridge. This is a functional native
successor, not an installed patch to the accepted release. Source-link the frozen
v3 core, wire, hooks and parent adapter and frozen card session/rules. Derive only
the binding and three native card adapters, preserving their existing type names
and namespace as source-compatible replacements in an explicit Compile closure.
Never compile both original and replacement types into one assembly. New assembly
identities identify this composition; no old package or policy is re-certified.

## Ownership after dispatch

Validate the live button's exact event/option binding and Godot liveness while
reserving it before ForceClick. Once reserved, retain that object solely as an
opaque receipt identity. Reservation is the final button-authority check; later
changes to that retired button's Event/Option getters are not inspected. Logical
event/option mutation tests target the bound model, option key and live context,
not properties of the retired presentation object. Do not dereference it or require native liveness from
post-dispatch capture, hook admission or child control. The exact option model,
run/player/run-state/room/layout/map/overlay, nonce and parent action remain bound.
Chosen must still match the exact reserved option under the exclusive hook lease
and inherited dispatch scope; request and creation must retain their causal scopes.
All predispatch deck, offer, preferences, task, screen, duplicate/replay and child
lineage checks remain. Retaining the managed receipt does not authorize clicking
it again, adopting another button/selector or accepting a foreign callback.

This change covers upgrade-one, removal1..8 and reward additions1..8. Parent/child
wire grammar, counts, confirmation, action budgets, exact effects and no-retry
semantics remain frozen v3. No new hooks, API family, diagnostic live route,
privileged fields, dependency or live filesystem access is introduced.

## Validation and ownership

Root owns contract, retained-evidence report, explicit build/checker/provenance,
native compilation and native-to-Python integration project/fixtures, final docs
and acceptance. Native implementer owns native/ replacement sources and
native_tests/ only after independent contract review. Reviewer owns read-only
contract and implementation review. One SDK lane; disposable /private/tmp outputs.

Fixtures must reproduce rejection with original native sources after button
removal/free, then demonstrate corrected upgrade/removal/add completion through
parent Proceed/map. Treat freed-button getters as throwing, not readable stubs.
Cover freeing before Chosen, after creation, delayed request/creation/completion,
ordinary parent-only transitions, retained receipt identity and no repeated clicks.
Preserve failures for invalid predispatch button, changed event/option/run/player/
layout/map/deck/offer, duplicate request, foreign or context-lost callback, and
child lineage. Rerun all550 preserved native assertions against the replacements.
Run actual native/wire-to-frozen Python composition and two byte-identical native
builds against exact pinned sts2/Godot/game-owned Harmony. Offline tests execute
only inert target stubs plus pinned Harmony; target assemblies remain compile-only.

Accept only after independent review, focused and integrated validation, exact
source/provenance manifest and frozen rerun. A later installable successor needs
its own release policy, production review, package, preflight and fresh campaign.
Do not claim this offline correction fixes the observed live failure without a
new live result. If another unsupported live transition remains, bounded fixed
reason codes belong in a separately reviewed diagnostic/release increment.
