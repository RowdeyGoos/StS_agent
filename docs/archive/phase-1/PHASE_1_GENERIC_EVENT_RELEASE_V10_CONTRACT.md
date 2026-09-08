# Generic event release v10: directly select card 16

2026-09-08. User explicitly asks to click one of cards16–20 without the earlier
visibility-boundary requirements. This supersedes v8/v9 clipping proof and the
handoff suggestion to introduce a viewport proof. Successor32 preserves all31
predecessors. This is a controlled test, not general scrolling support.

## Test behavior

Use existing native holder order; target zero-based slot15, the sixteenth card.
Mask only that slot as selectable and dispatch the existing holder._GuiInput
select action once. Do not scroll, search a clipping parent, read a viewport,
check layout dimensions, or require a geometry certificate. Remove the entire
GridGeometry/ProbeGeometry implementation from the derived transform adapter.
Retain allocated holder/model identity, native enabled/tree-visible state and
exact-original preview and selected-only transformation completion checks.
The user identifies row4/cards16–20 as off-screen in their controlled20-card
five-column setup. We record that setup, rather than prove it again in code.

A missing sixteenth holder or replaced/disabled target stops without clicking
another card. Existing holder/domain binding, parent/screen/task ownership and
bounded client remain; these protect target identity, not visibility boundaries.
No new reflection, private input path, signal emission or game model write.
Preview matching the exact original proves selection. Existing confirmation and
Proceed/map may complete the event; report selection separately if later steps
fail. No uncertain input retry or manual completion after an uncertain result.

## Release and validation

Derive generic_event_release_v9 as generic_event_release_v10, namespace
GenericEventReleaseV10, overlay/assembly Sts2AgentBridgeGenericEventV10 v1.0.0,
artifact root /private/tmp/sts-generic-event-v10-release, private operator
Sts2AgentBridge/generic_event_v10 and config generic_event_v10_transport_config_v1.
Campaign GENERIC-EVENT-V10-SMOKE-V1 and state root
Sts2AgentBridgeCampaign-generic-event-v10-smoke-v1 use fresh credentials/state.
Reject every predecessor campaign/operator/overlay conflict, including v9.
Retain G7 host, protocol, routes, journal and18 hooks; the same56 production
sources retain the v9 diagnostic vocabulary unchanged. Only the derived transform
adapter changes gameplay. Removed geometry APIs are forbidden by release verifier.

Root owns implementation, fixed-slot native/socket fixtures, source closure,
package/client/operations and documentation. Independent reviewer checks contract,
adapter/target identity and owns verifier changes. All SDK9.0.303 builds serialize
through root in fresh /private/tmp source snapshots using pinned cached references.
Production/game/Godot assemblies are not executed offline; test targets are inert.

Validate the actual slot15 native dispatch and exact preview/transformation,
missing/disabled/replaced target, deferred reassignment and uncertain response.
Run corresponding end-to-end client cases, release/transport/operator and
transactional install/cleanup checks, exact production policy and package tests.
Check frozen predecessor source identities; reuse previously accepted G7 regression
evidence instead of rerunning unrelated frozen gameplay suites. One complete
source-frozen aggregate plus the production pair and independent review is the
installation gate. Do not repeat entire candidate/frozen suites just for this
small test. No geometry-probe acceptance matrix remains a requirement.

## Live test

The user authorizes reversible preparation, exact owned installation and this
single test. Verify stopped game/closed bridge and unchanged429-file base before
installation. Install and verify the new overlay/operator files, then tell user
to start manually on Profile3, single-player, same window, ordinary20-card deck,
fresh Aroma of Chaos initial choices untouched and console/popups closed.
Do not add clipping-parent/viewport/size admission requirements to this setup.
After readiness verify initial screen, require-running and invoke the frozen
client once with the fresh state hash. It chooses Let Go then target slot15.
Do not automatically launch or access profile/save/Cloud data. Normal quit,
wait-stopped, code-first quarantine, exact four-file purge and final unchanged
base/stopped checks close the campaign. No redundant user approval is required.
