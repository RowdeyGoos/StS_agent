# Current unified release

This directory binds the current candidate to its source, tests and package.
[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns live
support; [bridge usage](../../README.md) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release validation, independent review and current live status |

Manifest SHA-256:
`00280cad681d0e074ec174ca548b273e1c77edfd58e838b10c6426f6a7827fe8`.
It binds **416 inputs across 51 projects** from the working checkout based on
`dbd7861`. DLL: **1,442,816 bytes**, SHA-256
`46b35765e7be4dbf77c1e2f7e504e4089461772ffd479af8d9d9a66b5f9ad2b0`.

The release gate passed **83 groups in 306.807 seconds**, including reproducible
build, shared socket requests, package verification and disposable owned
installation/cleanup. The full native regression passed 12,647 checks. Focused
Fake Mango validation passed 118 native checks, 33 client tests in 0.10 seconds
and the unified protocol gate in 13.382 seconds. Independent semantic review
completed at 20:05:32 UTC (253 seconds); both findings were corrected, with no
remaining blockers. Earlier reward/removal reviews and their exact evidence
remain in validation.json.

This candidate adds terminal screens with up to 32 reward entries (schema 9),
exact Fake Mango +3 max HP/+3 HP (schema 10), and selectorless native automatic
removal. Older reward bounds and the bounded `agent_v1` profile remain explicit.
These bridge corrections do not complete the full shared native interface.

**Installed and verified by 20:12:14 UTC on 2026-09-24, awaiting manual Profile 3
launch**: two exact overlays and all 429 base files unchanged. Installation-state
SHA-256: `b5c4a8b660aff7f471a26b566e5a31509702e7e423f9babf9583f5733dfaeef8`.

The preceding candidate read the original ten-entry Fake Merchant screen, then
stopped at its unrecognized Fake Mango effect (8/8/7 reward actions). No input
was retried; owned cleanup completed by 19:56:46 UTC. The earlier Dark Door
1/1/0 result retains its separate original identity and unknown rejected predicate.
Neither failed attempt is live proof of these corrections.

Gate and operational evidence are retained at `/private/tmp/sts-bridge-ktzq938k`;
install inputs are at `/private/tmp/sts-unified-bridge-release`. The gate's
`previous-*.json` files retain the preceding expanded-reward candidate. Git
`dbd7861` and the [M7 record](../../../../docs/evidence/AGENT_CAMPAIGN_M7_2026_09_24.md)
retain the accepted assisted campaign under its original package identity.
