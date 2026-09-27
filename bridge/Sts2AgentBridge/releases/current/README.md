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
These are fixture/build results; live floor-81 continuation remains outstanding.

Publish, stopped-game installation, exact overlay/base and installed metadata
checks passed by **2026-09-27 10:48:07 UTC**. Two exact overlay files are installed;
all 429 base files are unchanged. Installed state:
`b6ddfd36b730046504ec7f893fe9d9ae95feac721065347ec262541e7f275011`.
The game remains stopped for manual Profile 3 launch. The next test verifies the
restored saved state, then resumes the shared policy through combat, rewards and
map return. No fresh campaign is needed. Thirty-two disposable helper cases pass.

The preceding package passed the [86-card rest/map cycle at 14/14/14](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#large-rest-recovery-and-floor-81-stop-2026-09-27),
then stopped entering floor 81 at **27/27/26**, one pending map action. Normal
quit and exact cleanup passed by **10:31:01 UTC**; those counts remain unresolved.
Its full record is retained in Git `2fbb99a`, and its exact package inputs in
`/private/tmp/sts-bridge-2347lgir/previous-install-inputs`. Prior live results retain
their original artifact identities in the existing ledger.
