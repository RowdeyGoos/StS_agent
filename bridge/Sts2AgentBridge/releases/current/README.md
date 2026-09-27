# Current unified release

This release fixes full-navigation admission after floor 80 and preserves verified
completion receipts when a later native read or projection fails. Full mode uses
the nonnegative native floor counter; legacy campaign_v2 retains 0–80. Execution
budgets, native ownership and unresolved-action cleanup remain unchanged.

[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns support;
[bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, review, installation and separately bound live evidence |

Manifest SHA-256: `418330cff79f95d517596c27929ac84a3440693d0aed716da0de563cdda97149`.
It binds **485 inputs across 52 projects**, feature/source `2fbb99a` plus the
checker-generated package identity. DLL: **1,802,752 bytes**, SHA-256
`0f9cc8c8286a45abb3516cca46192a1c64e8a88777e975b2cc7c03c9871aeb91`.

The final gate passed **85 groups in 360.645 seconds**, including reproducible
builds, metadata/dependency checks, packaging and disposable cleanup. It includes
**168 client tests**, **1,642 router checks**, **284 campaign checks** and
**16,982 native event checks**. The final focused coordinator/router/client run
passed six groups in **17.659 seconds**. Independent source review took **318
seconds**. All 102 bound Python files match the preceding accepted release.
These are fixture/build results. The corrected floor-81 combat, rewards and map
continuation also passed live at **10/10/10**, with nothing pending. The next rest
stopped before input at the declared Clone capacity guard, preserving the verified
map receipt. The campaign ending remains open.

Publish, stopped-game installation, exact overlay/base and installed metadata
checks first passed by **2026-09-27 10:48:07 UTC**. After the live test, normal quit
and exact cleanup passed by **10:56:07 UTC**. Reinstallation and verification of
the same package passed by **10:57:23 UTC**. Two exact overlay files are installed;
all 429 base files are unchanged. Installed state:
`79001d017b36208ef30280a0a1f1908a378f66961f0b75294cf0ee02d986fe0e`.
The game remains stopped for manual Profile 3 launch. Before the next policy
attachment, the controlled setup will remove Pael's Growth and refresh the rest
options, retaining the 128-card bound. No fresh campaign is needed. Thirty-three
disposable helper cases pass. The [live ledger](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#floor-81-recovery-and-settled-clone-capacity-stop-2026-09-27)
records the accepted scope and cleanup.

The preceding package passed the [86-card rest/map cycle at 14/14/14](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#large-rest-recovery-and-floor-81-stop-2026-09-27),
then stopped entering floor 81 at **27/27/26**, one pending map action. Normal
quit and exact cleanup passed by **10:31:01 UTC**; those counts remain unresolved.
Its full record is retained in Git `2fbb99a`, and its exact package inputs in
`/private/tmp/sts-bridge-2347lgir/previous-install-inputs`. Prior live results retain
their original artifact identities in the existing ledger.
