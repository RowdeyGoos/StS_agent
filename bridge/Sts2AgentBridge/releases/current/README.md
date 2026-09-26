# Current unified release

This release fixes inherited passive-relic pickup hooks in the shared shop producer.
[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns live
support; [bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, review, installation and separately bound live evidence |

Manifest SHA-256: `e47f0514d5d7b142d247425f3aad227e9bdbe662b491f33809b36ab7c9e8e383`.
It binds **485 inputs across 52 projects**, source `c599a9f`.
DLL: **1,793,024 bytes**, SHA-256
`59a89110df5da538603b02e6b1a73796971e139ab6733d5490203a911c0e6f1b`.

The final gate passed **85 groups in 362.357 seconds**, including reproducible
builds, native metadata/dependency checks, packaging and disposable cleanup.
It includes **168 client tests**, **1,639 router checks**,
**229 event wire cases**, **16,829 native event checks**,
**656 rest checks**, **21 shop core checks**,
**252 campaign checks** and **179 potion checks**.
Independent semantic review found no remaining blocker. The focused regression
passed 301 native shop-effect checks and 21 shop core checks in five groups.
Original broad Python results remain separately bound; no new broad Python run is claimed.

Harmony now receives the declared pickup method for inherited callbacks; ownership
and cleanup inspect that same method. Fixtures cover actual inherited passive
relics, delayed completion and a conflicting patch rejected before purchase input.
The controlled Profile 3 retest passed: **3 attempted / 3 accepted / 3 reconciled**,
four controller reads and no pending action. The policy purchased Red Mask for
172 gold, closed the shop and returned to an actionable map. Exact pickup and
payment settled; HP, deck and potions stayed unchanged. A separate preflight read
and final inventory read are excluded from the four controller reads.
The [Red Mask ledger](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#red-mask-corrected-shop-purchase-passed)
records that test's setup, installation and cleanup.

The unchanged package then passed Kifuda's three-card shop pickup on **2026-09-26**:
**7 attempted / 7 accepted / 7 reconciled**, 25 controller reads and no pending
action. The three selected original Bludgeons each received Adroit 3, gold changed
466 to 254, one Kifuda was appended and the game returned to an actionable map.
Other cards, HP and potions were unchanged. One preflight and one final inventory
read are separate from the controller reads. The
[Kifuda ledger](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#kifuda-three-card-shop-pickup-passed-2026-09-26)
records the bounded sixteen-shop setup search; Cauldron/Orrery were absent and
remain untested. Other pickup selectors and Kifuda's zero/fewer-card and
deselection variants remain separate cases. Source and package identities were
verified before reuse; no new build or release-gate run is claimed.

The next unchanged-package batch passed Dolly’s Mirror (one exact Bludgeon clone),
Potion Belt (full inventory expanded to five slots, both new slots filled), and
Cook (Decay/Defend+ removal, deselection/reselection, +9 current/max HP). All three
returned to an actionable map with verified effects and unchanged unrelated
inventory. Counts were **45/45/45**, including legal travel between cases, with
no pending action. The [batch ledger](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#mirror-potion-belt-and-cook-batch-passed-2026-09-26)
records per-case counts, reads and limits.

The [rest-site batch](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#remaining-rest-options-and-smith-toggle-passed-2026-09-26)
then passed Lift, Kindle, Clone, Hatch and Dig in one Miniature Tent visit, followed
by Smith deselection/reselection at the next legally reached rest site. Exact
effects and map returns settled at **24/24/24**, including travel, with no pending
action. This closes representative successful coverage for all supported
single-player rest options; caller and variant limits remain in current status.

Latest normal Save and Quit, game Quit and exact owned cleanup passed by
**2026-09-26 10:27:28 UTC**: four generated files removed, zero overlays and all
429 base files unchanged. This batch's installed state was
`fe129e4dff9a5c059771be88800e667ccf8d7486cdf3c25d41c3a61424b8f1bb`.
Installation is now absent; the validated package is retained.

The preceding manifest `18169693…`, source `7bd3e09`, passed Neow’s Bones:
**7 attempted / 7 accepted / 7 reconciled**, 53 controller reads and map return.
Its later Red Mask purchase stopped with `uncertain_dispatch` at **1/0/0**, leaving
an unresolved action. No mutation was retried. Normal save/quit and exact cleanup
finished by **21:13:24 UTC**: four generated files removed, zero overlays and all
429 base files unchanged. These results retain their original identities in Git
`c599a9f`, the [live ledger](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md)
and `previous-release-record` under this release’s evidence directory.

The [native candidate boundary](../../../../docs/AGENT_CONTRACT.md#native-full-run-v2-candidate)
remains explicit. Remaining shop/rest/pickup cases, other compound Neow branches,
empty chests and a full v2 ending retain their stated evidence limits. No
profile/save/history/Cloud files or live trajectory corpus were accessed.

Current evidence is under `/private/tmp/sts-bridge-5hudfwrd`. Prior install inputs
are retained in its
`previous-install-inputs` directory; current install inputs use
`/private/tmp/sts-unified-bridge-release`.
