# Shop map permission V1 corrective release

This sibling implements the exact three-predicate repair selected in
`docs/PHASE_1_SHOP_MAP_PERMISSION_V1_CONTRACT.md` (SHA-256
`b9551348a73bd4ff54433dc9693cbed3ae841bb98bdc3f4763e22f1bcac613db`).
The observed merchant baseline has MapOpen=false, MapTravelEnabled=true and
MapTraveling=false. Initial/pre-Apply projection, purchase reconciliation and
inventory-close reconciliation now permit that baseline. All other session
bytes, including ReconcileLeave, are preserved. Closed+enabled after Proceed
remains terminal unsupported; no retry, FTUE query or later map adoption exists.

Production retains the exact loader identity/manifest Sts2AgentBridgeRoomFlowsV1
1.0.0 and 37 explicit source inputs. Only ShopV1Session is substituted; the other
36 frozen source inputs and every event/item/native/operator/runtime behavior
remain unchanged. The new DLL and policy hashes identify the correction. All
eight predecessor trees and the old48 bridge inputs remain frozen.

The pure core tests retain all13 predecessor groups and add one map-permission
boundary group. The actual wire/service/Python host fixture exercises the full
purchase/close/leave flow with permission enabled. Existing runtime/socket
fixtures retain their original baseline and run against the repaired core/wire.
The test-only policy delta checker verifies the three changed method bodies,
unchanged remaining methods/source inputs, and deterministic PE layout changes.
Neither production nor target game assemblies execute in offline acceptance.

Run check.py with the pinned SDK9.0.303, pinned two game-reference directory and
an absent direct child of /private/tmp as --scratch. It snapshots and verifies
all sources, builds production twice in physically separate roots, verifies
whole-assembly policy and mutation/CLI negatives, and runs the actual canonical
package, synthetic overlay, campaign-manager, client and cleanup fixtures.
The source_identity.json is the exact new source freeze. Full independent repeat
and local publication must pass before live installation.

Package root: /private/tmp/sts-shop-map-permission-v1-release.
Campaign: SHOP-MAP-PERMISSION-V1-SMOKE-V1.
State root: Sts2AgentBridgeCampaign-shop-map-permission-v1-smoke-v1.
The protected room_flows_v1 config directory, port43117, shop/event selection,
operator scope and fixed overlay remain unchanged. The manager additionally
rejects prior room/diagnostic states and diagnostic overlays, preserving them.
operations/source_derivation.json reconstructs all specialized operational,
client and package sources from hash-pinned frozen sources.

Live setup, after accepted installation with the game closed: Profile3,
Ironclad Ascension0, merchant inventory open with an affordable ordinary card,
untouched offers and no popup. Invoke the selected-flow client once with the
fresh installed-state hash. Accepted scope is zero/one ordinary-card purchase,
inventory close and leave, at most three reservations. No relic/potion/removal
purchase, rest upgrade, profile/save access, Cloud change, retained live corpus,
remote Git operation or uncertain-action retry is included.

Quit normally, verify stopped/closed, quarantine code first, purge exactly four
generated files and verify unchanged base429/zero-overlay/fixed absences within
30 minutes. Repeated unmodded relaunch is user-waived. No successful live control
claim follows from compilation, fixture acceptance or the earlier read-only
diagnostic. The acceptance ledger records the actual release/live disposition.
