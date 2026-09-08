# Generic event v7: variable-count transformation

2026-09-08. Proposed successor28 after the successful v6 singleton potion test.
User requested the next generic-handler feature. All27 predecessors and original
bridge remain frozen; all live campaigns are closed. This is functional work,
not a release, installation or live campaign.

## Scope and compatibility

Preserve G6 upgrade/removal/reward-addition/singleton-item functionality. Extend
transformation to positive variable selection counts: 1<=min<=max<=8, complete
eligible domain >max and <=64. New min<max admission requires native
RequireManualConfirmation=true and Cancelable=false. Existing fixed transforms
retain their accepted manual-confirmation behavior. Optional zero selection,
variable upgrade, scrolling, multi-item, linked/custom/terminal rewards and combat
remain excluded. Event names never determine admission.

Outer contract/version/routes become generic_event_v7 and generic-event-v7.
Transform children use card_transform_v2; derive a new transform core/journal,
codec and parser from frozen v1, without editing v1. All G7 transform children
use v2, including fixed-count ones. Card selection and item remain their actual
frozen engines and protocols. Public descriptor fields/order and correlation are
otherwise unchanged; no client-supplied native semantics. Preserve exact typed
version checks, full parent/child lineage, replay rejection, cumulative completion
and last-parent effects. Shared limits remain30s,2048reads,12parentactions,
4children,52totalattempts; at most8 selections+preview+confirm per card child.

## Native interaction contract

Reuse the18 existing observational hooks with original methods always executing.
No new target inspection or invocation of private game methods. Retained native
ConfirmSelection, RefreshConfirmButtonVisibility and _Ready evidence establishes
a distinct root-level Confirm that requests preview after min selection when
manual=true. The final %PreviewContainer/Confirm completes selection. At max,
the existing OnCardClicked path opens preview automatically.

Bind the root control alive by exact identity at admission; hidden/disabled below
minimum is legitimate. Visibility/enabled gates dispatch availability, not admission.
After preview dispatch its identity is an opaque receipt: do not require continued
visibility, enabled state or liveness of a legitimately retired root control.
Bind root screen.GetNodeOrNull<NConfirmButton>("Confirm") for variable transforms
only, separately from the existing preview final Confirm. Preserve exact root,
preview,grid,holder,card,model,player,run,request and task identities. Expose the
root button as the public preview action only after min and before max, with
visible/enabled control, settled selection and unchanged context/domain/deck.
Dispatch only its native ForceClick, with immediate fresh control/reference,
selection,foreground and geometry checks. Never directly call ConfirmSelection,
OpenPreviewScreen, transformation commands or delegate functions.

Before preview dispatch reserve the complete expected original selection set
and count. A preview is complete only when its before-side holders match that
exact set; reaching min while more holders are still appearing is insufficient.
For automatic preview at max, reserve before the final select dispatch the prior
selected identities plus the newly requested original as the expected set. Preserve those identities across asynchronous preview creation.
Reject replacement/foreign/duplicate nodes or clones, unexpected selection changes,
stale controls, reordered retained preview generations and context/task failures.
A valid earlier preview may contain fewer than max originals. Freeze its exact
holder/card/original identities at full expected membership, not at min alone.
Never expose more selections after preview has been requested.

Final Confirm independently validates that exact complete preview and reserves
its selected originals in TransformState within min..max before dispatch. Preserve
existing authoritative transformation journal: all selected originals removed,
per-card replacement generation/modification/final insertion, exact surviving
originals plus append reconciliation, partial asynchronous effects and final
owned request/Chosen tasks. No inference from equal card definitions or visual
replacement previews. Early selection completion must transform exactly the
chosen originals and preserve every unselected deck identity/upgrade level.

## Core, wire and host

New CardTransformV2Session relaxes only the fixed-count context restriction and
necessary variable preview assumptions. It retains current minimum/maximum
checks, action receipts, preview membership, immutable selection, pending control
validation, exact final journal and error/reentrancy/cleanup behavior. The new
wrapper implements G7's card child interface; preserve frozen ordinary card
wrapper and singleton item wrapper behavior.

G7 family admission and strict host/codec/parser permit variable transformation
only with preview_confirm; native manual=true is a private admission prerequisite.
At every producer/core/wire/host layer, a preview opening below max without an
accepted explicit preview action is unsupported, even if its membership matches.
ReconcileSelect must not accept that early-open transition. An early preview
envelope requires an accepted preview receipt, while automatic
max preview requires all max selection receipts. A provider may choose preview
as soon as it is legal or continue selecting. Neither layer auto-invents an early
finish or relaxes reconciliation. Wrong v1 transform tags, changed min/max/domain,
preview before minimum, missing preview receipt, late selection or mismatched
terminal originals stop without another POST. Lost/uncertain responses are never
retried. Completion counters must survive Proceed and later failure.

## Ownership and validation

Root owns this shared contract, scaffolding, all project files, checker, provenance,
README, living docs, integration acceptance and final source freeze.
B owns new native/*.cs and native_tests/*.cs plus native evidence analysis.
A owns new core/*.cs, transform_core/*.cs, wire/*.cs, host/*.py, wire_tests/*.cs,
transform_tests/*.cs and host_tests/*.py. R independently reviews contract first,
then owns integration/*.cs and integration_tests/*.py, and reviews root/A/B changes.
No lane edits frozen predecessors, project files or another lane's sources.
All agents use the active23cf worktree and serialize SDK work through root.

Preserve every G6 suite, updating only successor names/version expectations and
intentional formerly-rejected variable transform cases. Add pure core, wire,
host and actual-native-to-Python tests for selecting minimum, intermediate and
maximum counts; min2 and upper8 boundaries; manual=false variable rejection;
min0/invalid limits; pending/disabled/replaced root control; partial preview at min;
wrong/mutating membership; stale final confirmation; exact selected-only effects;
late task faults and replacement substitutions; held-out event identities;
variable transform followed by item/upgrade and Proceed; retained completion on
later failure; no retry after lost preview/final-Confirm responses.

Require independent review, focused tests, full actual-native integration, explicit
project/source closure, all27 predecessor identities, exact derivation/reuse records,
and two byte-identical production compilations per aggregate. Execute only inert
target stubs and pinned game-owned Harmony offline; never game/Godot/production
assemblies. Build only disposable /private/tmp snapshots with SDK9.0.303, no
network dependency or workspace outputs. Run candidate and source-frozen aggregate
gates, record exact results and limits, then update living docs. No live claim or
package follows automatically from functional acceptance.
