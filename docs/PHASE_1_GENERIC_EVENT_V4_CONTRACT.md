# Generic event v4 — fixed-count multi-upgrade and cumulative child evidence

2026-09-08. Proposed for independent review; consumers must wait for acceptance.
The user requests continued generic-handler development after v5's successful
Cheese/Gorge live path and complete cleanup. This is the next complete shared
family slice. All 23 predecessors and original bridge remain frozen.

## Functional successor and retained behavior

Create `generic_event_v4`, with GenericEventV4 types and `generic_event_v4` outer
protocol/routes. Preserve the frozen card_selection_v1 session and child payload.
Derive functional core/wire/host/integration from generic_event_v3; use the
corrected generic_event_lifecycle_v1 binding and generic_event_release_v5 native
adapters as the native baseline, with mechanical namespaces. Retain the seven
existing observed entry points, parent receipt lifetime fix and reward hitbox
compatibility repair. No event-name or option-key admission rows.

Upgrade now supports fixed min=max counts 1..8, preview_confirm, domain>max and
at most64. Preserve existing upgrade-one single preview. New counts2..8 require
the proved native multi-preview path. Retained OnCardClicked code opens that
preview only at max; no variable/minimum early-preview behavior is inferred.
Cancelable/zero-count, domain<=max selectorless paths, scrolling, transformation,
item children, custom/combat and unknown families remain unsupported. Removal
1..8 variable counts and reward add1..8 modes retain their accepted semantics.

## Authoritative multi-preview mapping and dispatch ownership

A clone's CloneOf, key, apparent similarity or slot order cannot prove its source.
The retained native path directly calls ICardScope.CloneCard, which does not set
CloneOf. A new observational scope must bind exact original arguments to exact
returned clone references while the owned NDeckUpgradeSelectScreen.OnCardClicked
call constructs its multi-preview. Use only the exact proved concrete RunState
clone method; require the captured run-state identity and compatible exact type.
Bind both authoritative manual-confirmation preference values without inventing
an early-preview action. Original methods always execute. No argument/result replacement, transpiler,
private-field read, inferred mapping or global clone adoption.

Before dispatching a native candidate, reserve one ticket bound to the existing
child admission, exact selector, holder, original and owner thread. The ordinary
native input dispatch remains the mutation. Its possibly deferred OnCardClicked
callback consumes that ticket exactly once for that screen/original. Reject
missing/duplicate/foreign/replaced/reentrant callbacks; never adopt an arbitrary
user click or a callback from another scope. Preserve the ticket across a delayed
native callback, but invalidate it on close/dispose/failure; do not grant a second
selection while a ticket is outstanding. This is deferred callback correlation
under the existing single-controller ordering contract, not evidence that AsyncLocal
context survives the native queue or that indistinguishable same-holder native
callbacks carry an unforgeable queue token. Observations never mint tickets.
A lost/throwing dispatch is uncertain
and is never retried.

Each valid callback advances the exact selected-original dispatch set. At the
final count, scope synchronous CloneCard calls to that callback and same run state.
Capture bounded unique original→clone pairs, reject a clone equal to an original,
wrong/duplicate originals or clones, missing/extra results and scope loss. Require
the complete pair domain to equal the expected selected set; do not commit a
partial preview snapshot. The scope closes before any public child observation.
Nonpreview clone calls confer no authority. Returned clone references are retained
only for this bound preview generation and cannot be reused by another child.

Validate the actual multi-preview container, Cards children, preview holders,
NCard models and Confirm control against that immutable mapping. Preview holders
must be complete, unique and form an exact bijection with returned clones; each
mapped original must match the selected receipt set independently of native slot
or click order. Check original keys/levels against baseline and preview clone's
expected upgrade, and retain exact holder/card/control references once bound.
Wrong/replaced/dead/invisible controls, replaced clones, changed originals,
partial membership, stale generation and any extra preview child stop before
Confirm. Use typed hitbox liveness plus retained-reference binding for the new
multi-upgrade path, as in the accepted reward repair. Preserve the single-upgrade
path except explicitly reviewed shared mechanics required to add the new branch.

Native Confirm remains the sole commit. Selector and request results must be
bounded max+1 exact selected-original snapshots; the owned Chosen task must
succeed and selector close. The frozen card core verifies unchanged ordered
baseline originals and keys, exactly+1 upgrade on each selected original, no
unselected change and monotone partial progress. No other event effects are
certified. The callback/mapping design must be independently accepted against
rehashed retained metadata before implementation; any missing exact signature or
causal mapping requires a separately reviewed bounded static inspection.

## Public cumulative evidence

Preserve `effects` as the existing last-parent-action field. Add
`completed_card_children`, integer0..4, to v4 parent observations and host summary.
It counts only fully validated child resolutions; later Proceed, unsupported or
uncertain parent actions do not erase that evidence or certify their own effects.

Core increments exactly once on the first valid resolved ReadChild result,
guarded by the resolved-delivered flag, before returning it. Repeated core reads
cannot increment again. Wire and host validate the parent count against their
previously validated count at the start of each GET, then increment their local
count only after fully validating that envelope's first child_resolved response.
This addresses the parent-before-child sampling order with one precise envelope
lag, never a blanket plus/minus-one allowance. The next parent snapshot must
match the updated count, including unsupported/map states. Parent child_completed
history rows must correspond to distinct validated completed lineages: history may
trail the count by at most one, only for the latest accepted parent owner, during
child disposal/parent cleanup failure. Ready/complete or a new parent dispatch
require equality. A lost or malformed terminal child payload earns no host credit.
Repeated resolved
child envelopes retain their existing rejection; repeated completed parent reads
are stable. Public count must not exceed admitted episodes or validated lineage.
Reject forged/regressing/skipped/out-of-range counts before further dispatch.

Unknown POST outcome or later failure retains previously validated cumulative
count. No raw card identities, credentials, diagnostic internals or hidden game
state are added. Deeply immutable providers, legal-action validation, exact
ordered histories and lineage remain. Keep12 parent actions,4 children,52 total,
10 actions/child,2048 reads and the existing30-second host deadline.

## Ownership and validation

Root owns this contract, checker, source/project/dependency closure, derivation,
README and living documentation. Native lane owns native/, native_tests/ and a
retained native-evidence report, except root-owned project/derivation files.
Consumer lane owns core/, wire/, host/, host_tests/ and wire_tests/, except
root-owned projects. Integration lane owns integration source and integration_tests,
except root-owned projects. Independent reviewer reviews the contract and complete
native/consumer/integration deltas. SDK lane is serialized and assigned explicitly.

Retain existing functional tests and add actual native hooks→card core→wire→Python
cases under unrelated and held-out event identities. Cover fixed2 and8, domain>max,
reverse click/slot order, asynchronous parent/screen setup, deferred click, preview
creation and upgrade completion. Reject variable upgrade counts, early/max-incomplete
preview, missing/duplicate/foreign/replaced/stale clones, wrong run/screen/original,
lost scope and duplicate callbacks, mutated controls or originals, wrong task sets,
unselected/+2/reordered deck changes and lost final Confirm without retry. Verify
cleanup ownership and failed hook install/unpatch recovery for all new targets.
Keep old upgrade-one/removal/reward native cases and derived reward hitbox coverage.
Add cumulative count cases for resolved child→Proceed→map, duplicate reads,
multiple children, unsupported/uncertain later action and forged wire responses.
Pure policy/core fixtures do not substitute for actual native composition.

Use only pinned game-owned Harmony with inert stubs offline. Production adapter,
sts2 and Godot assemblies are compile-only. No network dependencies or target
execution. Build disposable snapshots under /private/tmp using SDK9.0.303; verify
all predecessor identities, explicit production/test source closure and exact
provenance, run focused/integrated suites and two identical native builds. Independent
acceptance and full candidate gate precede source freeze; rerun full frozen gate.
No package, listener, installation or new live campaign is part of this functional
slice. Update coverage honestly; a separate reviewed release can later exercise it.
