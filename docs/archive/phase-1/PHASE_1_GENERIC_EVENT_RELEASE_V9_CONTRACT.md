# Generic event release v9: diagnostic repair for off-screen test

2026-09-08. User requests fixing the v8 geometry stop so testing can continue.
Successor31 derives v8 and preserves all30 predecessors and the original bridge.
The v8 live result proved no card dispatch; it did not identify its failing check.
This increment repairs that diagnostic gap without claiming the unknown geometry
cause is fixed or relaxing selection eligibility.

## Scope and exact substitutions

Use GenericEventReleaseV9, Sts2AgentBridgeGenericEventV9 version1.0.0,
Sts2AgentBridgeGenericEventV9-1.0.0.zip, /private/tmp/sts-generic-event-v9-release,
operator generic_event_v9, config generic_event_v9_transport_config_v1,
campaign GENERIC-EVENT-V9-SMOKE-V1, and state directory
Sts2AgentBridgeCampaign-generic-event-v9-smoke-v1. Reject all prior operator,
state and overlay conflicts, including v8. No credential or state identity reuse.

Retain G7 core/protocol/routes/host, transformation V2 journal and18 hooks.
Replace exactly the v8 transform adapter and the old v5 diagnostic enum/codec
with v9-owned derivations, keeping their namespaces/types so frozen callers
remain unchanged. The production closure stays56 sources. All other gameplay
bytes remain exact. Preserve v8 full expected-card coverage and its validated
fully-below-clip mask, including per-dispatch revalidation, exact originals in
preview and selected-only transformation completion. No scroll/mouse fallback,
reflection, private invocation, direct signals, model writes, new target API,
new runtime geometry getter, raw observation or numeric geometry payload.

Diagnostics do not authorize actions. Append values78–114 to the old closed
0–77 vocabulary, preserving every old integer and string. Propagate local out/ref
diagnostics through the existing geometry helper calls, preserve read order,
short circuit and the same number of geometry sampling passes. Set the stage
before potentially throwing geometry reads. A reported code identifies the
failed or throwing check/stage; it is not proof a specific comparison returned
false. No new global or cross-request diagnostic state. Existing cached native
LastDiagnostic and authenticated HTTP header convey the value; Python transport
accepts only the exact enlarged finite vocabulary, and the existing sanitized
summary returns it. Body schema and host policy stay unchanged. Unknown enum
values map to diagnostic_unavailable; malformed/unknown headers still fail.

## Appended diagnostic vocabulary

- 78: `GeometryCandidateCount` / `geometry_candidate_count`
- 79: `GeometryScrollMissing` / `geometry_scroll_missing`
- 80: `GeometryScrollInvalid` / `geometry_scroll_invalid`
- 81: `GeometryScrollInvisible` / `geometry_scroll_invisible`
- 82: `GeometryScrollSize` / `geometry_scroll_size`
- 83: `GeometryScrollPosition` / `geometry_scroll_position`
- 84: `GeometryGridSize` / `geometry_grid_size`
- 85: `GeometryCardSize` / `geometry_card_size`
- 86: `GeometryYOffset` / `geometry_y_offset`
- 87: `GeometryColumns` / `geometry_columns`
- 88: `GeometryScrollHeightMismatch` / `geometry_scroll_height_mismatch`
- 89: `GeometryScrollPositionMismatch` / `geometry_scroll_position_mismatch`
- 90: `GeometryClipSearchInvalid` / `geometry_clip_search_invalid`
- 91: `GeometryClipSearchCycle` / `geometry_clip_search_cycle`
- 92: `GeometryClipSearchDepth` / `geometry_clip_search_depth`
- 93: `GeometryClipMissing` / `geometry_clip_missing`
- 94: `GeometryClipRect` / `geometry_clip_rect`
- 95: `GeometryCanvasInvalid` / `geometry_canvas_invalid`
- 96: `GeometryChainInvalid` / `geometry_chain_invalid`
- 97: `GeometryChainNonCanvas` / `geometry_chain_non_canvas`
- 98: `GeometryChainCycle` / `geometry_chain_cycle`
- 99: `GeometryChainDepth` / `geometry_chain_depth`
- 100: `GeometryChainUnreached` / `geometry_chain_unreached`
- 101: `GeometryTopLevel` / `geometry_top_level`
- 102: `GeometryCanvasMismatch` / `geometry_canvas_mismatch`
- 103: `GeometryTransform` / `geometry_transform`
- 104: `GeometryNodeRect` / `geometry_node_rect`
- 105: `GeometryControlRect` / `geometry_control_rect`
- 106: `GeometryClipChanged` / `geometry_clip_changed`
- 107: `GeometryParentChanged` / `geometry_parent_changed`
- 108: `GeometryTransformChanged` / `geometry_transform_changed`
- 109: `GeometryNodeClipChanged` / `geometry_node_clip_changed`
- 110: `GeometryRectChanged` / `geometry_rect_changed`
- 111: `GeometryMaskCount` / `geometry_mask_count`
- 112: `GeometryInitiallySelected` / `geometry_initially_selected`
- 113: `GeometryCandidateInvisible` / `geometry_candidate_invisible`
- 114: `GeometryNoneEligible` / `geometry_none_eligible`

ClipChanged covers retained clip validity, clip flag or clip rectangle mismatch.
NodeRect is finite ancestor geometry; ControlRect is positive holder/card/hitbox
geometry including finite endpoints. Transform covers finite axis-aligned positive
basis; TransformChanged covers mismatch against the retained basis. NoneEligible
means no candidate with both existing Enabled and the fully-below mask true.
These grouped predicates are explicit diagnostic stages, not raw target values.
MaskCount is the retained mask/domain length check. Successful preparation still
reaches ChildReady, and subsequent parent completion reaches MapReady.

Preserve boundary semantics: clip at depth32 is allowed; nonclip at depth32
rejects. Ancestor rectangles remain finite-only; candidate and clip rectangles
remain strictly positive. Partially clipped candidates may coexist with eligible
ones and must not cause an early rejection. Preserve final Probe.Matches and
Mask.Matches sampling and dispatch-time proof; no extra diagnostic sampling.
Unexpected changes and uncertain input still stop without retry.

## Ownership and gates

Root owns release scaffold, project closure/checker, enum/codec, runtime/transport
consumers and tests, integration Python expectations, operations/package/client,
provenance/freeze, artifacts and living docs. A bounded geometry implementation
agent owns only gameplay/GenericEventV7TransformAdapter.cs and gameplay_tests/
OffscreenFixtures.cs and TargetStubs.cs, plus integration/OffscreenSocketFixture.cs
if native fixture additions require it. Independent reviewer owns verifier/
and verifier_tests/ changes and policy review; root builds and generates policy.
Read docs/MULTI_AGENT_EXECUTION.md before dispatch; no agent live work. Serialize
SDK9.0.303 builds through root in fresh /private/tmp snapshots with pinned cached
references. Production is compiled only; inert target stubs execute offline.

Require native negative-stage coverage, deterministic first-failure precedence,
unchanged v8 admission/action/preview/completion/race cases, exhaustive enum/header
vocabulary, unknown values, diagnostic reset and actual-adapter socket-to-Python
failure summaries with zero card dispatch. Add verifier negative mutations for
the appended vocabulary while retaining API restrictions and exact whole-assembly
policy. Frozen G7 regressions remain separate evidence. Run complete candidate
and source-frozen aggregate gates, all30 frozen inventories, complete provenance,
two identical production builds per aggregate, package/lifecycle/conflict/cleanup
fixtures and independent review before installing. No result from inert fixtures
constitutes live selection success.

## Live preparation and bounded test

The current user request authorizes necessary reversible preparation and owned
installation for the next test. After all gates, require stopped game/closed port
and clean429-file base. Install and verify exactly the new overlay and operator
files, then tell user to manually launch Profile3, single-player, same window,
ordinary20-card deck, fresh Aroma of Chaos initial choices untouched and console/
popups closed. Do not adopt the earlier open selector or promise geometry passes.
No automatic launch or profile/save/Cloud access. Runtime geometry admission still
determines whether this setup contains an eligible fully clipped allocated card.

After user readiness, fresh UI and running checks precede exactly one frozen
client invocation with the fresh state hash. Retain parent choose0 of2 and child
first_legal policy; success requires exact child completion and parent continuation.
If admission fails, retain the more specific sanitized code; never bypass it or
retry uncertain input. Normal quit, wait-stopped, code-first quarantine, exact
four-file purge and final unchanged clean-base/stopped checks close the campaign.
No redundant confirmation is needed for this requested testing preparation.
