# Current unified release

This directory owns the **accepted artifact identity and validation binding**.
[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns the
latest operational result, installation record and capability limits;
[bridge usage](../../README.md) owns build/install/client/cleanup commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Accepted validation and retained live/cleanup evidence bindings |

Manifest SHA-256:
`cb2d91104d8cab404a0000f004e0d0dcef9b5850cff2e8273425e27c043a20b0`.
It binds 359 exact source/test inputs captured from the working checkout based on
`7334873`. That original build provenance is retained after the implementation
commit `cd3dc76`; documentation edits do not repin the manifest.

The accepted gate passed **71 groups in 262.450 seconds**, including reproducible
production build, package and owned installation/cleanup checks. Independent
semantic review and focused native/client/codec/unified/socket checks preceded it
(11,432 native checks; 192.284 seconds). The release includes the exact terminal
Fake Lee’s Waffle healing and freed reward-button reconciliation corrections.

The [September 12–13 ledger](../../../../docs/evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md)
retains original failed attempts and later passes under their own releases.
Earlier manifests and test counts are not evidence for a different artifact.
