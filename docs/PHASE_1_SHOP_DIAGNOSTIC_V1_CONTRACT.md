# Shop Diagnostic V1 contract

Status: selected implementation contract, 2026-09-06 local / 2026-09-05 UTC.
The user said proceed after the accepted zero-action shop rejection and cleanup
at integration head 1aa2018c73462250ce59aa183884e3c1ba7d439a.
This is one passive diagnostic observation, not a controller repair or gameplay
capability. Preserve all seven frozen successor trees and all 48 old bridge
inputs. New source only: bridge/Sts2AgentBridge/successors/shop_diagnostic_v1.

## Purpose and passive derivation

Distinguish the first rejected native CaptureSurface/helper or initial
ObserveReadySurface/TryProject predicate from the frozen shop implementation.
The diagnostic uses only the already-authorized native reads in their existing
evaluation order; it adds no target member, filesystem or game-state query.
Retain fail-closed logic. Do not infer the historical failure from the screenshot
or weaken a predicate to accept it. Never reconstruct discarded response bytes.

Production is passive-only. Derive a new native reader and pure first-read
projector; do not compile the frozen whole ShopV1Session or native adapter.
Exclude Apply, CapturePending, pending reconciliation, purchase dispatch classes,
ForceClick, _GuiInput, input synthesis and purchase event subscriptions. Replace
only the presence of inert action wiring with internal readiness facts, whose
static provenance is checked. Do not perform an action or synthesize a success
receipt. Keep ephemeral captured values/private identities inside the reader;
the network result contains no content, keys, prices, gold, object identities,
exception text, logs or counts.

A checked-in deterministic derivation manifest and executable source checker
must bind the selected original methods/expressions, ordering and explicit
omissions to the frozen originals. Each transformation must be independently
reviewable. Pure tests compare the passive projector to the actual frozen
first-read session on authored captures with test-only inert dispatch sentinels.
The production candidate excludes that reference session and all test stubs.
Stubbed-native tests compile the actual new adapter and exercise getter order,
short-circuiting, malformed/transitional slots and exceptions. Tests do not
execute Godot/game assemblies. These prove specified parity, not live success.

## Shared API and ownership

Namespace Sts2AgentBridge.Successors.ShopDiagnosticV1. The coordinator owns
shared/IShopDiagnosticService.cs: public IShopDiagnosticService : IDisposable
with byte[] Observe(). A owns core/, reader/, reader_tests/ and derivation/:
passive contracts/projector/recorder/codec/service, actual adapter, provenance
and tests. Constructor ShopDiagnosticService(IShopDiagnosticAdapter adapter),
with ShopDiagnosticNativeAdapter implementing that pure adapter interface.
The service captures one observation on its owner frame, projects once, returns
one owned byte array, and releases private references on owner disposal.
No repeated capture, callback, subscription or independent thread is allowed.

B owns runtime/, runtime_tests/, operator/, operator_tests/, lifecycle_tests/ and
native/: restricted runtime, secure operator, bootstrap host/factory and tests.
Use exact source links to reusable accepted lifecycle/interfaces, timer support,
Godot connector, build guard, descriptor and authenticator kernels where their
boundaries fit. Production factory constructs only
new ShopDiagnosticService(new ShopDiagnosticNativeAdapter()).
R owns verifier/, verifier_tests/ and policy/ and independent review. Root owns
remaining transport/client, operations, packaging, production project, aggregate
checker, source freeze and documentation. Writers never touch another lane or
any predecessor. No agent independently installs or invokes a live campaign.

## Fixed diagnostic record

Exactly five ordered fields, compact ASCII JSON, maximum 512 bytes:
{"schema_version":1,"status":"passed","shop_status":"unsupported","stage":"native_offers","reason":"cost_text_invalid"}

status=passed means the diagnostic observation completed, not that the shop is
supported. shop_status is ready, waiting or unsupported. ready requires
complete/none. waiting is original Missing behavior and preserves the first
native_context failure reason; an authored missing capture may use
core_surface/surface_missing. unsupported preserves the first rejection or
exception stage. The recorder is instance-owned, first-failure-wins and accepts
only fixed enums. It cannot retain or serialize arbitrary text. Exception paths
report native_exception or projection_exception with the last entered stage;
no exception message/type/stack leaves the service. Generic transport/client
failures use a separate fixed bounded failure record and claim no diagnosis.

Stage allowlist:
native_context, native_deck, native_controls, native_foreground, native_offers,
core_surface, core_context, core_deck, core_offers, core_inventory, complete.

Reason allowlist:
none, run_unavailable, room_unavailable, room_singleton_mismatch,
global_ui_unavailable, map_unavailable, map_singleton_mismatch,
inventory_node_unavailable, room_model_unavailable, inventory_model_unavailable,
player_unavailable, inventory_model_mismatch, current_room_mismatch,
deck_count_out_of_range, deck_card_unavailable, deck_count_changed,
back_control_unavailable, merchant_control_unavailable, proceed_control_unavailable,
overlay_stack_unavailable, overlay_count_out_of_range, offer_count_out_of_range,
offer_slot_unavailable, offer_hitbox_unavailable, offer_entry_unavailable,
card_model_unavailable, relic_model_unavailable, potion_model_unavailable,
cost_label_unavailable, cost_text_invalid, native_exception, surface_missing,
surface_unsupported, context_unavailable, gold_out_of_range, room_not_visible,
foreground_blocked, map_open, map_travel_enabled, map_traveling,
initial_binding_invalid, deck_binding_invalid, offer_slot_invalid,
offer_order_invalid, offer_key_invalid, offer_price_invalid, offer_not_visible,
offer_identity_invalid, offer_identity_duplicate, card_binding_invalid,
card_already_in_deck, noncard_binding_invalid, inventory_not_open,
inventory_not_visible, back_control_not_ready, projection_exception.

Production never invokes the frozen session for parity; that is a test-only
reference. Any recorder/projector disagreement fails the offline gate rather
than becoming another allowed live response.

## Single-read runtime and secure startup

Public ShopDiagnosticTransportRuntime.Create(byte[]? configuration,
Func<byte[]?> credentialReader, Func<IShopDiagnosticService> factory); same
Start, DrainFrame, StopTransportAndJoin, TransportStopped,
DisposeServiceOnOwnerFrame, ServiceDisposed, IsTerminalOrStopping ownership
contract as accepted room runtime. No nonce generation is needed: one fresh
credential and one fixed endpoint bind this sole exchange. Parse exact protected
configuration before credential read, factory or listener startup; zero consumed
arrays defensively on every path. Construct on owner frame only.

Exactly one route, GET /probe/shop-diagnostic-v1/public/diagnostic.
No POST, decision/action headers, item route, generic route callback or retry.
Preserve exact canonical ordered ASCII HTTP/authentication, head cap 4096,
half-close/EOF, listener 127.0.0.1:43117, bounded header/write/connection timeouts,
pre-authentication 32/s burst16, handler cap4 and owned frame queue discipline.
Reserve the single authenticated lifetime observation before rate/queue work.
A second/competing authenticated exchange terminalizes without another observe.
Malformed or unauthenticated requests never invoke the service. Any claimed
exchange outcome is terminal; publish stop only after attempted response send,
buffer cleanup and socket close. Lost delivery never permits another capture.
Observe runs at most once on the Godot owner frame. Stop/join network first,
then dispose service on owner frame, then detach the Godot frame connection.
Off-thread timers/ProcessExit cannot dispose native state or claim full cleanup.
The inherited five-second bootstrap timeout is pre-first-frame only; no active
listener TTL expires while the user navigates. Tests use ephemeral loopback and
must reject port43117. SHOP_DIAGNOSTIC_TEST_SEAM is absent from production.

Fixed protected directory:
~/Library/Application Support/Sts2AgentBridge/shop_diagnostic_v1
Exact enabled config, no newline:
{"schema_version":"shop_diagnostic_v1_transport_config_v1","enabled":true,"bind_address":"127.0.0.1","port":43117,"token_file":"credential.hex"}
Missing, disabled, malformed, old-scope or extra-field config fails closed before
credential read. No flow selection flag or current-screen inference exists.

## Release, operations and live boundary

One Sts2AgentBridgeShopDiagnosticV1 1.0.0 DLL and exact manifest, canonical stored
ZIP at /private/tmp/sts-shop-diagnostic-v1-release. One initializer; explicit
compile links, no satellite DLL/project reference in production, only the two
pinned compile-only game references. Whole-assembly source/metadata/IL policy
requires exactly the diagnostic GET route, rejects gameplay action methods,
member refs/routes, test stubs/seams and unexpected native imports. Extraction
is test-only, shipping verifier consumes independently frozen policy. Require
mutations and two matching fresh candidate builds without executing candidate
or target assemblies. Verify all seven predecessors and old48 in the new gate.

Campaign ID SHOP-DIAGNOSTIC-V1-SMOKE-V1; state root
Sts2AgentBridgeCampaign-shop-diagnostic-v1-smoke-v1; overlay root
Sts2AgentBridgeShopDiagnosticV1. Specialize accepted transactional operations,
including immutable state/config binding, UID501, descriptor/ACL/inode checks,
exclusive creation, code-first quarantine and exact four-file purge. Reject and
preserve every legacy/item/room/diagnostic operator, overlay or campaign conflict.
Synthetic manager/client/package and actual base/overlay checker fixtures are
required. The fixed live client accepts only --expected-state-sha256, verifies
source and installed state, transfers credential once and performs one GET with
a 10-second outer deadline. Validate the exact record allowlists and combinations,
zero buffers and print only that bounded record or fixed failure. No polling.

Only after independent acceptance and exact published artifacts: fresh stopped/
closed, base429, conflict-absence and package preflight; install while closed;
verify exact overlay; ask the available user to launch Profile3/continued run,
open the merchant inventory and leave it untouched. This read-only diagnostic
may use the saved unchanged shop from the prior zero-action campaign. It does
not repeat a prior uncertain action. Verify supported UI setup, invoke once,
then normal UI quit, stopped/closed, exact quarantine/purge and final base429/
zero-overlay/absence. Campaign bound30minutes including cleanup. Repeated
unmodded relaunch remains user-waived. Record sanitized outcome only. No profile/
save filesystem access, Cloud change, retained live corpus, remote Git or broader
capability change. The user's proceed instruction selects this diagnostic;
it does not waive any implementation, review or live cleanup gate.
