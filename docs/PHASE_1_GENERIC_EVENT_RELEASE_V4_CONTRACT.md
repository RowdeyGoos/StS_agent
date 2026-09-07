# Generic event release v4: reward candidate diagnostics

2026-09-07. User-authorized continuation after the closed v3 campaign. The
reviewed seven-body and single-model-method inspections did not establish a
candidate-admission defect. This contract selects diagnostic-only v4; it does not
claim a repair. Independent contract review precedes implementation. Keep the
game closed until the new release and installation gates pass.

## Purpose and inherited boundary

The closed release-v3 live campaign stopped at `prepare_candidates`, before any
child action, and completed cleanup. That result identifies a preparation helper,
not its failing leaf. This successor only distinguishes existing reward candidate
preparation checks. It does not change candidate admission or claim a fix.

Inherit the accepted `docs/PHASE_1_GENERIC_EVENT_RELEASE_V3_CONTRACT.md` and its
complete security, gameplay, transport, cleanup, ownership and evidence boundaries
except for the exact deltas below. Preserve the original bridge and all twenty-one
frozen successor trees; accepted release v4 will be successor twenty-two. Do not
edit a predecessor to simplify derivation or to make a fixture pass.

Frozen gameplay core, card session, hooks, lifecycle binding, wire protocol and
Python host remain source-linked. Gameplay protocol remains generic_event_v3;
release identity becomes v4. No event catalog, changed operation family, predicate
relaxation, additional game getter, reflection, native traversal, Capture, hook,
identity fallback, raw observation, index, key, count, shader value, geometry,
exception text, profile/save/Cloud access or target-game execution offline.

## Exact finite extension

Preserve enum member names, numeric values and wire strings 0..36 from v3.
`NotCaptured=0` still maps to `none`; `DiagnosticUnavailable=36` remains the
fallback. Append only the following 41 members. Each wire value is explicit,
unique ASCII lower snake case of at most 32 characters; never use Enum.ToString
or serialize arbitrary text.

| Value | Enum member | Wire value | Existing failed check / active operation |
| --- | --- | --- | --- |
| 37 | `CandidateExpectedNull` | `candidate_expected_null` | An expected original model is null. |
| 38 | `CandidateExpectedDuplicate` | `candidate_expected_duplicate` | The expected-original reference set rejects a duplicate. |
| 39 | `CandidateDisplayedNull` | `candidate_displayed_null` | The first holder.CardModel read does not produce a CardModel. |
| 40 | `CandidateUnexpectedModel` | `candidate_unexpected_model` | The displayed model is absent from the expected-original reference set. |
| 41 | `CandidateDisplayedDuplicate` | `candidate_displayed_duplicate` | The displayed-original reference set rejects a duplicate. |
| 42 | `CandidateModelNull` | `candidate_model_null` | The second holder.CardModel read is null. |
| 43 | `CandidateCardNull` | `candidate_card_null` | The captured holder.CardNode is null. |
| 44 | `CandidateHitboxNull` | `candidate_hitbox_null` | The captured holder.Hitbox is null. |
| 45 | `CandidateHighlightNull` | `candidate_highlight_null` | The captured card.CardHighlight is null. |
| 46 | `CandidateCardType` | `candidate_card_type` | The card fails the existing exact-runtime-type predicate. |
| 47 | `CandidateCardInvalid` | `candidate_card_invalid` | The card passes exact type but fails existing Godot liveness. |
| 48 | `CandidateHitboxType` | `candidate_hitbox_type` | The hitbox fails the existing exact-runtime-type predicate. |
| 49 | `CandidateHitboxInvalid` | `candidate_hitbox_invalid` | The hitbox passes exact type but fails existing Godot liveness. |
| 50 | `CandidateHighlightType` | `candidate_highlight_type` | The highlight fails the existing exact-runtime-type predicate. |
| 51 | `CandidateHighlightInvalid` | `candidate_highlight_invalid` | The highlight passes exact type but fails existing Godot liveness. |
| 52 | `CandidateMaterialNull` | `candidate_material_null` | The existing highlight.Material read returns null. |
| 53 | `CandidateMaterialKind` | `candidate_material_kind` | The same non-null material value is not a ShaderMaterial. |
| 54 | `CandidateMaterialType` | `candidate_material_type` | The assignable ShaderMaterial fails the existing exact-runtime-type predicate. |
| 55 | `CandidateMaterialInvalid` | `candidate_material_invalid` | The material passes exact type but fails existing Godot liveness. |
| 56 | `CandidateStableKey` | `candidate_stable_key` | The existing stable-key validation fails. |
| 57 | `CandidateDomainCount` | `candidate_domain_count` | The constructed binding count differs from the expected-original count. |
| 58 | `CandidateDomainBounds` | `candidate_domain_bounds` | The binding count fails the existing 2..64 bounds. |
| 59 | `CandidateSnapshotCount` | `candidate_snapshot_count` | The holder-snapshot count differs from the binding count. |
| 60 | `CandidateHolderIdentity` | `candidate_holder_identity` | A snapshot holder is not the original binding holder. |
| 61 | `CandidateHolderType` | `candidate_holder_type` | The bound holder fails the existing exact-runtime-type predicate. |
| 62 | `CandidateHolderInvalid` | `candidate_holder_invalid` | The bound holder passes exact type but fails existing Godot liveness. |
| 63 | `CandidateModelIdentity` | `candidate_model_identity` | The existing snapshot holder.CardModel read differs from the bound model. |
| 64 | `CandidateCardIdentity` | `candidate_card_identity` | The existing snapshot holder.CardNode read differs from the bound card. |
| 65 | `CandidateHitboxIdentity` | `candidate_hitbox_identity` | The existing snapshot holder.Hitbox read differs from the bound hitbox. |
| 66 | `CandidateHighlightIdentity` | `candidate_highlight_identity` | The existing snapshot card.CardHighlight read differs from the bound highlight. |
| 67 | `CandidateMaterialIdentity` | `candidate_material_identity` | The existing snapshot highlight.Material read differs from the bound material. |
| 68 | `CandidateKeyChanged` | `candidate_key_changed` | The existing snapshot stable-key equality fails. |
| 69 | `CandidateLevelChanged` | `candidate_level_changed` | The existing snapshot upgrade-level equality fails. |
| 70 | `CandidateShaderRead` | `candidate_shader_read` | The existing shader-width read/conversion/classification throws. |
| 71 | `CandidateHighlightUnsettled` | `candidate_highlight_unsettled` | The original post-snapshot allSettled gate fails. |
| 72 | `CandidateInitiallySelected` | `candidate_initially_selected` | The original initial-candidate selected predicate fails. |
| 73 | `CandidateHolderInvisible` | `candidate_holder_invisible` | The original initial-candidate visibility predicate fails because holder visibility was false. |
| 74 | `CandidateCardInvisible` | `candidate_card_invisible` | The original initial-candidate visibility predicate fails because card visibility was false. |
| 75 | `CandidateHitboxInvisible` | `candidate_hitbox_invisible` | The original initial-candidate visibility predicate fails because hitbox visibility was false. |
| 76 | `CandidateEnabledRead` | `candidate_enabled_read` | The existing native hitbox.IsEnabled read throws. |
| 77 | `CandidateNoneEnabled` | `candidate_none_enabled` | The original final any-enabled threshold fails. |

The same card, hitbox, highlight and material type/liveness codes apply if those
existing checks fail during binding creation or the later snapshot. The codes
identify a leaf category, not a candidate index or a new observation. Holder
checks in the earlier `TrySnapshotHolders` helper remain `PrepareHolders`; do not
broaden that helper merely to manufacture coverage of these codes.

Invalid enum normalization must now recognize exactly 0..77. Do not retain the
old upper-bound comparison to DiagnosticUnavailable, because value 36 is no
longer the maximum. Every invalid integer and provider exception still yields
DiagnosticUnavailable=36. Append the same 41 strings to Python's strict response
header allowlist. Keep one required `X-Sts2-Native-Diagnostic` header, its existing
position, length budgets, authenticated-response validation and final
`last_response_diagnostic` semantics. No gameplay JSON changes.

## Instrumentation and predicate precedence

Only the reward adapter candidate preparation path receives new diagnostic
semantics. Pass a finite out-code through its existing `TryCreateBindings`,
`TryCaptureBindings` and `InitialCandidatesValid` path as needed. The parent
publishes its existing cached LastDiagnostic only on completed Capture. Child
constructors and ongoing child surface captures discard helper diagnostics as
before. Retain all existing catch/return behavior. A code assigned before a
throwing operation denotes that operation; do not catch and perform extra game
reads to explain an exception. Failures outside the covered leaf operations retain
the applicable existing broad code.

“First failure” means the first existing admission check reached in the frozen
short-circuit execution, including deferred snapshot checks. It does not mean the
first unfavorable value observed in any slot. Preserve the following exactly:

1. Iterate expected originals and test null, then reference-set duplicate, in
   existing order. For each holder, preserve the first holder.CardModel read,
   expected-set membership and displayed-set duplicate tests. Preserve the second
   holder.CardModel read; do not merge these two getter calls.
2. Preserve upfront reads of model, card, hitbox and `card?.CardHighlight` before
   their original null-check chain. Decompose that chain without moving a read or
   checking null earlier. Split exact type and Godot liveness only in their
   original short-circuit order. Read highlight.Material exactly once at that
   check and classify its cached result as null, incompatible kind, exact-type
   mismatch or failed liveness; classification must not reread the property.
3. Keep the original key validation read. CandidateBinding construction still
   rereads model.Id.Entry and reads CurrentUpgradeLevel at the original positions;
   do not reuse a cached validation key or move constructor reads. Preserve count
   mismatch before bounds and existing assignments of bindings/candidates.
4. Snapshot each slot in the existing structural order: holder identity; holder,
   card, hitbox, highlight and material exact type/liveness; model, card, hitbox,
   highlight and material identity; key equality; level equality. Only then read
   and classify shader width, evaluate holder/card/hitbox visibility with the
   original short circuit, read native IsEnabled, and construct the candidate.
   Set the shader-operation code immediately before the existing shader read and
   the enabled-operation code immediately before the existing IsEnabled read.
5. Preserve the full scan unless an original structural check or exception would
   stop it. In particular, do not return early on transient highlight, selected
   state, invisibility or a disabled candidate. Keep a bounded diagnostic-only
   per-slot array beside the existing candidate array, capped by the unchanged
   maximum domain of 64. Record the first false visibility operand as its existing
   expression evaluates; never evaluate a skipped operand. This sidecar is not
   part of any gameplay DTO, binding, wire body or host state.
6. After a successful full snapshot, test allSettled first, as before. Only then
   run initial-candidate validation in original slot order, testing selected
   before visible. Consume the corresponding saved visibility reason only when
   the existing visible predicate fails. Aggregate enabled with the same existing
   operations and report CandidateNoneEnabled only at the final failed threshold.
   That threshold is at least one enabled candidate, not minSelect.

Thus an invisible early slot plus a transient later slot reports
CandidateHighlightUnsettled, because allSettled precedes initial visibility
validation. A later structural failure defeats both deferred conditions. Within
an initially selected and invisible slot, CandidateInitiallySelected wins. A
successful path retains the existing ChildReady/parent/map result and never
publishes a temporary leaf code. Diagnostic setters/sidecar writes must not add
or suppress any native getter, validity check, action dispatch or enumeration.

## Minimal successor derivation and source closure

Derive a new `generic_event_release_v4` tree from frozen release v3 with an exact
path/import/identity derivation ledger. New public release namespace:
`Sts2AgentBridge.Successors.GenericEventReleaseV4`. Native classes retain their
original GenericEventV3 type names to compose frozen code.

The four native replacements remain explicit in production and inert native
socket/test project closures. Parent, upgrade-card and removal files receive only
the mechanical release-enum namespace import change. Reward receives that import
change plus the bounded candidate diagnostic instrumentation above. Do not replace
unrelated upgrade/removal helpers, change their gameplay behavior, or introduce a
mixed v3/v4 enum compatibility shim. Keep lifecycle binding and all other frozen
production gameplay sources source-linked. Record hashes and inspect exact diffs
for these three mechanical files separately from the reward semantic diff.

Derive the enum, explicit codec, Python finite allowlist, namespace references,
factory/runtime composition and release identities as necessary. Runtime sampling
still occurs exactly once immediately after Handle in the same owner-frame queue
operation. Workers never call the provider; timed-out/detached responses cannot
publish a late diagnostic. Preserve once-bound provider ownership and retryable
owner-frame cleanup without an additional runtime provider or second wire service.

New assembly/manifest/overlay `Sts2AgentBridgeGenericEventV4`, version 1.0.0;
stored two-entry package `Sts2AgentBridgeGenericEventV4-1.0.0.zip`; artifact root
`/private/tmp/sts-generic-event-v4-release`; campaign `GENERIC-EVENT-V4-SMOKE-V1`;
state `Sts2AgentBridgeCampaign-generic-event-v4-smoke-v1`; operator
`generic_event_v4`. Preserve old conflict rejection and additionally reject v3
state/overlay/operator remnants. Never adopt prior state or credentials. Generate
new artifact sizes/hashes after reproducible builds; no v3 artifact pin is reused.
Client retains only `--expected-state-sha256` and validates all 21 predecessors
plus the new frozen source/contract before credential use. Update the checked
source closure and derivation for the 22-component chain.

## Ownership and acceptance

Root owns contract acceptance, production project closure, checker, client,
package, operations, derivation and documentation. B owns enum, native replacements,
factory and diagnostic native fixtures. A owns runtime except enum, transport,
runtime/transport tests and the existing socket integration project. R owns
independent source/contract review, verifier policy and mutation review. No shared
write ownership; one SDK lane with explicit handoff. Work only in disposable
offline build snapshots. No additional target inspection is included.

Preserve the existing project/test categories and assertions; new checks are
additive. At minimum retain v3's 745 instrumented lifecycle assertions, 168 focused
diagnostic assertions, 38 release-native assertions, 373 runtime assertions,
17 Python transport tests and all 15 socket scenarios. Preserve the frozen
predecessor suites and operator/client/manager/conflict/package/clean-install/
verifier coverage through the full aggregate. Acceptance reports exact observed
counts; do not replace those retained assertions with equivalent-looking totals.

Add focused native evidence for each of the 41 appended codes, with one failing
leaf and valid earlier prerequisites. Exercise duplicate/membership/count failures
and temporal getter counterexamples with inert stubs, without loosening production
checks or directly assigning LastDiagnostic. For type-vs-liveness pairs, assert
that liveness is not read after a type mismatch. For the material cases assert one
property read. For the two CardModel creation reads and constructor key reread,
use sequenced getters proving both the call count and the expected failure branch.

Compare the sequence of original observable getter/validity/enumeration/dispatch
operations against the frozen v3 reward path on the same synthetic inputs. Use
isolated fixture projects or processes if identical native type names prevent a
single assembly comparison; the frozen source remains unedited. Include successful
admission; an early invisible slot with a later transient slot; an early transient
slot with a later structural failure; selected plus invisible; holder/card/hitbox
visibility short circuits; all-disabled and partly-enabled candidates; and a later
shader/IsEnabled exception. Assert original outcomes, side effects, selected
originals, timing/order and getter counts, alongside the new diagnostic. Verify
per-slot diagnostic storage does not change gameplay DTOs or publish indices.

Extend the existing actual-native-to-socket-to-Python fixture with at least one
new candidate leaf (prefer an exact-type mismatch from a controlled inert subtype,
with otherwise valid ownership and admission prerequisites). Compose actual
replacement native hooks/adapters, frozen core/session/wire, owner-frame runtime
and strict Python transport. Assert finite header/final summary propagation,
retained gameplay waiting/failure accounting, no child dispatch, and cleanup.
Retain the original 15 scenarios and their exact accounting. Do not substitute a
controller fake for this full-chain leaf case.

Test all 78 mappings, old 0..36 stability, values 37 and 77 accepted and -1/78
normalized to 36, invalid/throwing provider behavior, header rejection and prior
last-response retention. Update the exact enum/codec/owner-frame metadata and IL
policy and mutations. Two byte-identical compile-only production builds, independent
review, complete aggregate, source freeze and repeated frozen aggregate remain
mandatory. Only pinned game-owned Harmony plus inert stubs execute offline;
production assembly, sts2 and Godot stay compile-only. No new target inspection
is implied by test construction or by missing fixture metadata.

## Subsequent campaign boundary

After independent acceptance and release gates, inherit the v3 campaign's bounded fresh
installation, manual user launch, one controller, no retry after uncertainty,
finite sanitized result and exact normal-quit/quarantine/purge/clean-base closure,
using only the new v4 identities. Keep the game stopped until those release and
installation gates pass. Root must publish the accepted contract and fresh artifact
pins before any operational step. Persistent user authority covers this bounded development and one fresh live
campaign after all gates. No new capability, profile access, foreign-mod change
or approval flow is introduced.
