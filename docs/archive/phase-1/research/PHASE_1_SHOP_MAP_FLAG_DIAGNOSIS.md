# Shop map-permission predicate diagnosis

**Date:** 2026-09-06. **Disposition:** independently reviewed diagnosis and
minimal repair recommendation; the controller repair is not implemented yet.
The [live diagnostic ledger](PHASE_1_SHOP_DIAGNOSTIC_V1_ACCEPTANCE.md) records the
single accepted unsupported/core_context/map_travel_enabled result and completed
cleanup. No campaign remains active.

## Finding

The shop core incorrectly requires map travel permission to be disabled while
the merchant inventory is open or closing. On the pinned game build, the merchant
room deliberately enables that permission when it initializes. An enabled
permission is distinct from the map being open or travel being in progress.

This conclusion combines new live first-failure evidence with previously
accepted static IL; no new target extraction or target execution was needed.
Root reverified ten existing output files against the exact hashes in
[MR API selection](PHASE_1_MISSING_ROOM_API_SELECTION.json) and
[shop/event API selection](PHASE_1_SHOP_EVENT_API_SELECTION.json).
A traced native semantics, R independently reviewed contract and fixture
implications, and both agreed on the final three-predicate recommendation.

## Pinned static proof

- NMerchantRoom._Ready gets the map at IL292, pushes true at297 and calls
  SetTravelEnabled at298. This happens during ordinary merchant initialization.
- NMapScreen.SetTravelEnabled's true path calls the existing
  Hook.ShouldProceedToNextMapPoint at10, stores its result at18 and refreshes
  point visuals at24. Its getter only returns the backing field. No hook body
  was followed; the new live diagnostic directly confirms true in this shop.
- OpenInventory disables Proceed at15-20, opens inventory at26-31, disables
  Merchant at37-42 and connects InventoryClosed at53-76. It does not clear map
  permission. The close callback enables Merchant at1-6, enables Proceed at12-17
  and pulses Proceed at23-29, again without clearing permission.
- Proceed's normal dispatch is synchronous: ForceClick emits Released, which
  _Ready connects to HideScreen. HideScreen first calls MerchantFtueCheck; a
  true result returns, while false calls NMapScreen.Open(false) at9/14/15.
- NMapScreen.Open checks the existing IsOpen flag and, when closed, sets it true
  at10-12 before later UI work. Therefore a normal returned Proceed call already
  has an open map. Closed plus enabled afterward is the unchanged merchant
  baseline, not an evidenced asynchronous transitional state.
- NEventRoom.Proceed separately enables map travel immediately before opening
  the map. Shop evidence does not justify changing the event native, parent,
  child or final-Proceed preconditions.

| Existing static output | SHA256 |
| --- | --- |
| NMerchantRoom--_Ready.il.jsonl | `3cd577a770433c9e3aa16d752438c612986198159c84daa40b1ca0ae41c10fca` |
| NMerchantRoom--OpenInventory.il.jsonl | `d292a46ec1d813311d9313e6dfb59d6c7ba8086ea566166d7de25a139e0aae05` |
| NMerchantRoom--HideScreen.il.jsonl | `541e5abbb3fcf1bf623c7fe6c8589314b1f6883a7cdcdd59c8c97cb88a507b58` |
| NEventRoom--Proceed.il.jsonl | `aa9c384e4b020a0fb2854f669087c35485b06e7fd64032452b28cc6e05ea2cba` |
| NMapScreen--get_IsTravelEnabled.il.jsonl | `71f101040259adf46a8feeb535694c270cbe213f821562f4478b7f6a3608d563` |
| NMapScreen--SetTravelEnabled.il.jsonl | `777f625f1439a8b3a56b692ae600245ff13b293409525b4c974af68cc63d5c79` |
| NMapScreen--Open.il.jsonl | `6cce2c94086a0f5fa40c19f79e980a34bca7919db2ae09ee9412295dd4df4dbf` |
| NMerchantRoom--<OpenInventory>b__37_0.il.jsonl | `4bac7d8fc591b3f32c07f06f5934d244781cf449205816796a14e44691e8e454` |
| NMerchantRoom--MerchantFtueCheck.il.jsonl | `4f2a75e39ede1298f435fe95e0d13df4b86f388d44d343abce5ddfcd13175c03` |
| NClickableControl--ForceClick.il.jsonl | `c38c04b951e0fd5d60b3f78a62d82965989569e1a233d4c894b6786ab37b9dcb` |

## Minimal derived repair

In a new sibling implementation, derive the frozen ShopV1Session and remove
MapTravelEnabled from exactly three pre-leave rejection predicates:

1. TryProject, covering initial and immediate action revalidation as well as
   the room-ready-to-leave projection (current source line263).
2. ReconcilePurchase (line496).
3. ReconcileClose (line540).

Keep MapOpen=false, MapTraveling=false, all context/reference/visibility/control
and foreground checks, purchase effects, budgets, reservations and stale-binding
revalidation. Preserve native reads and every wire/host schema. Do not edit any
of the eight frozen source trees or reuse a historical campaign state.

Keep ReconcileLeave byte-exact. Same-context open+enabled+nontraveling resolves;
closed+disabled+nontraveling retains its existing bounded wait; closed+enabled,
traveling and other mixed states remain unsupported. Allowing closed+enabled
to wait would weaken the existing intercepted-FTUE/no-transition boundary and
could later adopt an unrelated map opening. No evidence warrants that change.
No profile/FTUE query, dismissal or retry should be added. Event remains unchanged.

Required fixtures should use closed+enabled as the ordinary shop baseline and
cover ready, purchase reconciliation, inventory-close reconciliation and
ready-to-leave. Preserve negatives for initial or pre-Apply MapOpen/MapTraveling
(with zero reservations/dispatch), and map opening/traveling during purchase or
close. Prove normal synchronous leave success, unchanged closed+enabled leave
terminal rejection after one dispatch, and no later map adoption after that
rejection. Preserve open+disabled and traveling negatives. Exercise the repaired
core through an actual service/wire/host fixture, then a separately reviewed
release/package before another fresh user-prepared shop live campaign.

This diagnosis does not prove later projection predicates will pass or establish
purchase/close/leave live acceptance. It does not classify the older controller
timeout. The passive diagnostic and existing gameplay contracts remain frozen.
