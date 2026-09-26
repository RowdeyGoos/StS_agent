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

The corrected package is installed and checked by **2026-09-26 12:08:59 UTC**:
two exact overlays and all 429 base files unchanged. Installed state is
`9f39f9df0369eeb78dad20d865dbc6b523c588f0a9f3bd5c72ead49bd2356d8a`.
The game was stopped before installation. Manual Profile 3 launch and a fresh
owned Punch Dagger test within the saved campaign remain pending; no new live
success is claimed for this package.

The preceding manifest `e47f0514…`, source `c599a9f`, passed Red Mask, Kifuda,
Dolly’s Mirror, Potion Belt, Cook, the remaining supported rest options, Smith
reselection and Yummy Cookie’s four-card upgrade. Its latest
[Punch Dagger attempt](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#punch-dagger-single-preview-failure-2026-09-26)
stopped with `read_native_failed` after buy/select at **2/2/0**, with no confirmation
or retry. Normal game Quit and exact owned cleanup passed by **11:54:51 UTC**;
cleanup does not resolve those actions. Native source/scene inspection and an
offline regression support the correction; the old live diagnostic did not expose
the exact rejecting predicate. The ledger retains each result’s original identity.

Current evidence is `/private/tmp/sts-bridge-6nkaloz2`. Its
`previous-release-record` and `previous-install-inputs` retain the preceding
records/package; Git `338a076` also preserves that release record. Current install
inputs are `/private/tmp/sts-unified-bridge-release`.
The [full-producer boundary](../../../../docs/AGENT_CONTRACT.md#native-full-run-v2-candidate)
remains explicit. Remaining concrete shop/pickup paths and a full v2 ending need
live acceptance. No profile/save/history/Cloud files or live corpus were accessed.
