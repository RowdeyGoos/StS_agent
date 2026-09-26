# Current unified release

This release fixes the shared single-card enchantment preview timing used by
shop pickups such as Punch Dagger and Royal Stamp. Native preview initialization
queues old children for deletion until frame end. The bridge now waits for that
cleanup during its owned input, then validates the exact original, clone and
enchantment before publishing selection or permitting confirmation. A changed
already-bound preview still fails; ownership, deadlines and cleanup remain strict.

[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns support;
[bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, review, installation and separately bound live evidence |

Manifest SHA-256: `289fabed66cddcd01003747383962f0c18f9a17395d2eb6c4a1b340bb4c5b302`.
It binds **485 inputs across 52 projects**, source `7829456`, feature `338a076`.
DLL: **1,793,024 bytes**, SHA-256
`91182c7940b4ce420841eece40292213479838f9240a20add75523f250639405`.

The final gate passed **85 groups in 355.485 seconds**, including reproducible
builds, native metadata/dependency checks, packaging and disposable cleanup.
It includes **168 client tests**, **1,639 router checks**, **229 event wire cases**,
**16,857 native event checks**, **656 rest checks**, **21 shop core checks**,
**252 campaign checks** and **179 potion checks**. Focused validation passed
877 pickup checks, 39 direct-input checks and six native enchantment integration
cases. Independent semantic review found no blocker in 193 seconds.
One earlier gate stopped because a second inert test stub lacked the deletion
API; it was corrected before the accepted gate. Original broad Python evidence
remains separately bound; no new broad Python run is claimed.

The corrected [Punch Dagger retest](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#punch-dagger-corrected-preview-passed-2026-09-26)
passed **7/7/7** through purchase, selection, deselection, reselection, confirmation
and shop/map return. The same original Bludgeon+ received Momentum 5, gold changed
1017 → 829, and the other cards/HP/potions stayed exact. There were 19 controller
reads, one preflight read and one final verification read, with no pending action.
Normal Save and Quit, game Quit and exact owned cleanup passed by
**2026-09-26 12:20:28 UTC**, leaving zero overlays and all 429 base files unchanged.

The subsequent [Gnarled Hammer/zero-purchase batch](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#gnarled-hammer-and-zero-purchase-shop-passed-2026-09-26)
passed **25/25/25** including legal travel. Hammer applied Sharp 3 to two Bludgeon+
originals and Headbutt+ for 204 gold; a later shop Close/Leave preserved exact
inventory without purchases. Cleanup passed by **12:34:12 UTC**, with zero
overlays and all 429 base files unchanged. The same accepted binary/gate was reused.

The [Royal Stamp test](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#royal-stamp-preview-toggle-passed-2026-09-26)
then passed **7/7/7**, including deselection/reselection. Defend+ received Royally
Approved with Innate and Retain; gold changed 826 → 614 and other cards/HP/potions
stayed exact through map return. Cleanup passed by **12:42:36 UTC**, with zero
overlays and all 429 base files unchanged. All five supported shop card selectors
now have a representative live success.

The [Orrery batch](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#orrery-five-card-rewards-and-merchant-travel-passed-2026-09-26)
passed **13/13/13** through five card additions, automatic shop return and map exit.
The helper's explicit-dismissal assumption caused a settled stop after eleven
actions; Close/Leave completed separately without repeating the purchase.
Later legal travel reached another merchant at **28/28/28**, with one confirmed
non-mutating stale rejection. Cleanup passed by **13:00:51 UTC**, leaving zero
overlays and all 429 base files unchanged. No production change was needed.

The subsequent [Cauldron attempt](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#cauldron-helper-stop-and-expired-purchase-2026-09-26)
stopped at **3/3/2** after a helper omission left the reward purchase pending.
The existing 60-second deadline expired during continuation preparation; no
further mutation followed its failed read. Normal game Quit and cleanup passed
by **13:10:43 UTC**, preserving the unresolved result. The helper now alternates
legal original-potion discards and claims; production sources remain unchanged.

The [corrected Cauldron retest](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#cauldron-five-potion-replacement-passed-2026-09-26)
passed **13/13/13** through all five protected-original potion replacements and
shop/map return. Gold changed 665 → 454; all 23 cards and HP 88/88 stayed exact.
Fourteen controller reads plus preflight/final verification found no stale or
pending action. Cleanup passed by **13:18:15 UTC**, with zero overlays and all
429 base files unchanged. The earlier 3/3/2 attempt remains unresolved separately.

The [Silver Crucible empty-chest test](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#silver-crucible-empty-chest-passed-2026-09-26)
passed **2/2/2** through Open/Proceed with exact inventory preservation and an
actionable map. Eighteen controller reads plus preflight/final verification found
no stale rejection or pending action. The installed state was
`b8e6c5b2b911e13ab3fbbef3b4b5641c91f2a4925feda4855c3acc5f0f48350a`.
Normal Save and Quit, game Quit and exact cleanup passed by **13:31:05 UTC**,
leaving zero overlays and all 429 base files unchanged.

The [Trial setup](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#trial-direct-shop-setup-rejected-2026-09-26)
stopped at **0/0/0** with `read_native_event_parent_travel`; console entry retained
the saved shop's enabled travel flag. No verdict/selector input ran. Normal Quit
and exact cleanup passed by **13:41:37 UTC**, with zero overlays and unchanged
base files. The next setup enters a connected room normally before creating Trial.

The same package was reinstalled and checked by **13:43:10 UTC**: two exact
overlays, unchanged base files and verified metadata. Installed state is
`9e5515310e7078abc5bc50a2eb44bc88d73bcf0d8da9a934a0846bd5a207dfa5`.
Manual Profile 3 main-menu readiness is pending; the saved campaign can be continued.

The preceding manifest `e47f0514…`, source `c599a9f`, passed Red Mask, Kifuda,
Dolly’s Mirror, Potion Belt, Cook, the remaining supported rest options, Smith
reselection and Yummy Cookie’s four-card upgrade. Its latest
[Punch Dagger attempt](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#punch-dagger-single-preview-failure-2026-09-26)
stopped with `read_native_failed` after buy/select at **2/2/0**, with no confirmation
or retry. Normal game Quit and exact owned cleanup passed by **11:54:51 UTC**;
cleanup does not resolve those actions. Native source/scene inspection and an
offline regression support the correction; the old live diagnostic did not expose
the exact rejecting predicate. The successful retest above does not reconcile the
old attempt. The ledger retains each result’s original identity.

Current evidence is `/private/tmp/sts-bridge-6nkaloz2`. Its
`previous-release-record` and `previous-install-inputs` retain the preceding
records/package; Git `338a076` also preserves that release record. Current install
inputs are `/private/tmp/sts-unified-bridge-release`.
The [full-producer boundary](../../../../docs/AGENT_CONTRACT.md#native-full-run-v2-candidate)
remains explicit. Remaining concrete shop/pickup paths and a full v2 ending need
live acceptance. No profile/save/history/Cloud files or live corpus were accessed.
