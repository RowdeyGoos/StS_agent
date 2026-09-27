# Current unified release

This release fixes rest-site handoffs after deck growth. Full-profile rest entry
and selectors now support the existing 128-card public inventory bound; legacy
routes retain 64. Clone's predicted result is checked before input. Verified
rest/shop receipts reach the client before a successor read can fail. Shared
selectors also handle native allocation cycling under the same bounded pan.

[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns support;
[bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, review, installation and separately bound live evidence |

Manifest SHA-256: `da706c27c151f0e8e1d286a1f16dc48a0770ec17f04e69598b677979f944b3dd`.
It binds **485 inputs across 52 projects**, feature/source `1f74e08` plus the
checker-generated package identity. DLL: **1,802,240 bytes**, SHA-256
`3d1a78ac7a3e166372bc1f45d109d7c00ce73edecfeb720f1327e73846c165dd`.

The final gate passed **85 groups in 356.419 seconds**, including reproducible
builds, metadata/dependency checks, packaging and disposable cleanup. It includes
**168 client tests**, **1,642 router checks**, **694 rest checks** and **16,982
native event checks**. The final focused pickup run passed **956 checks in 4.239
seconds**. Independent source reviews took **513 seconds** across diagnosis,
implementation and the allocation-cycle correction. The only changed bound
Python file is the tested agent failure-code consumer; the other 101 are unchanged.
These checks are fixture/build evidence; the live result is recorded below.

Installation, exact overlay/base verification and installed metadata checks passed
by **2026-09-27 10:16:59 UTC**. Two exact overlay files were installed; all 429 base
files were unchanged. Installed state:
`13420352011a5c163e0559333bb4a02a01da87d6d9648f934e879ed9f5f31aa8`.
The user manually launched Profile 3. The saved rest restored 63 cards and all
options, so the helper was adapted before input; **31 offline helper cases**
passed. The unchanged shared policy completed Smith, Heal/reward, Dig, Cook,
Kindle, Clone and Leave at **14/14/14**, with Clone adding 24 cards to reach 86
and a verified map return. This is a fresh test session, not adoption of the
preceding unresolved action.

Continuation completed the next shop, then stopped while entering floor 81 at
**27/27/26**, one pending action. The final public action was `choose_map_node`;
no combat decision was published. Source inspection found full navigation's old
80-floor guard and receipt loss on the subsequent failed read. Normal quit and
exact cleanup passed by **10:31:01 UTC**: four files purged, zero overlays and
all 429 base files unchanged. Corrected navigation and ending acceptance remain
outstanding; these counts are not retrospectively reconciled.

The preceding package passed [large Cook at 7/7/7](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#large-deck-cook-retest-passed-2026-09-27)
on a public 32-card deck. Its unchanged-policy route reached Act 2, then stopped
at an 86-card rest at **236/234/233**, one pending action. The final action was
not logged; Clone is a source-consistent explanation, not an observed action.
Normal quit and exact cleanup passed by **09:49:02 UTC**. Cleanup does not reconcile
that attempt. Its full original record is retained in Git `1f74e08`, with exact
package inputs in `/private/tmp/sts-bridge-gi4ihmno/previous-install-inputs`.
All prior live results retain their original artifact identities in the ledger.
