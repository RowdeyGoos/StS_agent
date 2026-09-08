# Shop map permission V1 repair contract

Selected 2026-09-06 after the user said continue at clean integration head
676afd45c15ad718f28c328d3681a4d0cf6becac. The accepted live diagnostic and
pinned-static diagnosis are in research/PHASE_1_SHOP_MAP_FLAG_DIAGNOSIS.md.
This increment implements and packages that exact shop-only repair. Preserve
all eight frozen successor trees, their contracts and the old 48 bridge inputs.
New source only: bridge/Sts2AgentBridge/successors/shop_map_permission_v1.

## Semantic change

Derive core/ShopV1Session.cs from the frozen room_flows_v1 ShopV1Session using
exactly three checked replacements: remove MapTravelEnabled from the rejection
predicates in TryProject, ReconcilePurchase and ReconcileClose. Every other byte
of the derived session must match the frozen source. Keep MapOpen, MapTraveling,
foreground, context/reference, card/gold/deck effects, control readiness, stale
revalidation, action reservations/budgets and reconciliation unchanged.

ReconcileLeave remains byte-exact: action-bound same-map open+enabled+nontraveling
resolves; closed+disabled+nontraveling retains its bounded wait; closed+enabled,
traveling and other mixed states remain unsupported. After normal synchronous
Proceed, closed+enabled is the unchanged baseline and may signal interception;
never wait for or adopt a later unrelated map opening. Add no FTUE/profile query,
dismissal, retry, action, target member, native read, wire field or host change.
All event/item/native/runtime behavior remains byte-exact.

This successor replaces only the original closed-map/travel-disabled shop
pre-leave requirement for this derived implementation. The preserved functional
contract continues to own all other shop/event action and wire semantics.
Shop still supports zero/one affordable ordinary-card purchase, inventory close
and room leave, with at most three reservations. No relic/potion/removal shop
purchase, rest upgrade or broader capability is selected.

## Composition and owners

A owns core/, core_tests/ and derivation/: the exact derived session, a pure core
project linking frozen ShopV1Contracts/CanonicalEncoder and Common, meaningful
positive/negative fixtures and deterministic original-to-derived source checker.
The core project is Sts2AgentBridge.ShopMapPermissionV1.Core. Existing public
namespace/types and wire-facing API remain unchanged. Keep the complete frozen
shop test suite and add the required map-permission cases.

B owns wire/, integration/ and runtime_tests/: a pure wire project linking the
two frozen room wire source files, the repaired core project, frozen broker and
event core; an actual C# service fixture using closed+enabled as ordinary shop
baseline; and a runtime test project linking the full frozen runtime fixture
source to the repaired wire/core. Reuse the real frozen Python host and socket/
cross-language fixtures against these replacement assemblies. No test stubs,
synthetic callbacks or fixture routes enter production. Native/game assemblies
are never executed by offline validation.

R owns verifier/, verifier_tests/ and policy/ and independent review. Reuse the
accepted whole-assembly room verifier/IL decoder/metadata semantics, update only
exact artifact/source policy bindings in the new tree, and prove changed method
bodies are limited to the selected session changes plus deterministic metadata
identity. Include shipping CLI negatives and actual PE mutation tests. Policy
extraction stays test-only; the shipping verifier consumes a frozen policy.

Root owns production project, properties, operations/client, package, aggregate
checker/source freeze and documentation. Production has the same explicit 37
Compile inputs as room_release_v1, with exactly one substitution: new derived
ShopV1Session replaces the frozen session. The other 36 source inputs are linked
byte-exact. No production ProjectReference, test constants or extra code source.

Keep loader assembly/manifest identity Sts2AgentBridgeRoomFlowsV1 version1.0.0,
its exact manifest bytes, protected room_flows_v1 directory/config selection,
endpoint and controller limits. This is a hash-bound corrective package of the
same capability. Its exact DLL, source inventory, verifier policy and distinct
artifact/campaign roots identify the revision; no old artifact is overwritten,
adopted or usable with the new manager. The unchanged event selection remains
available with exactly its prior scope, while this campaign selects shop.

New artifact root: /private/tmp/sts-shop-map-permission-v1-release.
Campaign ID: SHOP-MAP-PERMISSION-V1-SMOKE-V1.
State root: Sts2AgentBridgeCampaign-shop-map-permission-v1-smoke-v1.
Overlay path remains the fixed Sts2AgentBridgeRoomFlowsV1 directory; any existing
overlay, operator parent or old/current campaign state is rejected and preserved.
In addition to old/item checks, explicitly reject prior room and diagnostic
campaign state and diagnostic overlay conflicts. Preserve UID501, exact protected
config/flow binding, descriptor/inode/ACL validation, fresh credential, exclusive
publication, immutable state lineage, code-first quarantine and exact purge.
Derive operational sources by an executable exact original/hash/replacement
manifest; do not introduce a generic installer or mutable plugin mechanism.

## Acceptance

A deterministic derivation gate proves only the three exact session changes
and unchanged ReconcileLeave. Positive fixtures use MapOpen=false,
MapTravelEnabled=true, MapTraveling=false for initial ready, purchase, close and
ready-to-leave, while retaining compatibility with permission=false. Negatives
cover initial or pre-Apply MapOpen/MapTraveling with zero reservation/dispatch,
purchase/close map transitions, synchronous leave success, unchanged
closed+enabled leave rejection after one dispatch, no later map adoption after
terminalization, and open+disabled/traveling leave failures. Preserve the full
predecessor shop suite. At least one real service/wire/host flow must exercise
the repaired core from a closed+enabled baseline through purchase/close/leave.

Verify all eight predecessor source inventories and old48, exact reviewed
project/source closure and build controls, pure test dependency boundaries,
complete production metadata/IL policy, actual PE mutations and shipping CLI.
Make two fresh physical source/reference builds and require identical production
bytes; independently repeat complete acceptance. Run relevant regression. Use
pinned .NET9.0.303 offline with the same two compile-only game references. Check
actual final canonical package and actual synthetic base/overlay installation,
manager/client fault paths, old-scope conflict preservation and teardown. Freeze
new source only after review and final pins; publish the exact three artifacts
exclusively after acceptance. No target/candidate execution during these gates.

## Live gate

The user retains bounded live-campaign authorization. Ask availability only
when the accepted release is ready. Keep the game closed for fresh source,
package, base429, stopped/closed and conflict preflight and installation. Verify
the exact overlay, then ask the user to continue Profile3 Ironclad Ascension0,
open a fresh/saved unchanged merchant inventory with an affordable ordinary card,
and stop with offers untouched and no popup. The last diagnostic made no gameplay
action, so that saved shop is suitable. Verify supported game UI and invoke the
fixed selected-flow client exactly once with new installed-state hash. Never
retry the old uncertain controller action or any uncertain new dispatch.

Record only the accepted bounded action summary and sanitized visible evidence.
Quit normally via supported UI; verify stopped/closed; quarantine code first;
purge exactly four generated files; verify unchanged base429/zero-overlay and
fixed absences within 30 minutes of installation. Repeated unmodded relaunch is
waived. No profile/save filesystem access, Steam Cloud change, retained live
corpus, remote Git operations or broader capability change is authorized. A
first successful projection does not establish purchase/close/leave acceptance;
report any partial outcome exactly and clean up before further diagnosis.
