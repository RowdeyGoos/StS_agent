# Current unified release

This directory binds the current package to its source and validation.
[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns live
support; [bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, independent review, installation and live status |

Manifest SHA-256: `812c148b2cf224a3fd5a0d77c35be4f5e9cbbe07e1373123330e3e3c65a10364`.
It binds **439 inputs across 51 projects**, source `53e2255`, feature `49a6de1`.
DLL: **1,567,744 bytes**, SHA-256
`2d4a719865ee4037b6ebbb0a39b5b8c1619504df8a0c55a1719c9c02d45c79c5`.

The final release gate passed **83 groups in 317.947 seconds**, including
reproducible builds, native metadata/dependency checks, packaging and disposable
installation/cleanup. It includes **164 client tests**, **1,628 router checks**,
**13,372 native regression checks**, **656 rest checks**, and the actual-listener
full-graph/2,048-slot/nested-receipt test. These are offline checks. The focused
router suite passed in 13.443 seconds; independent semantic review passed in
23 seconds. The earlier full Python result remains historical evidence for its
original source; affected checks and the release gate ran for this correction.

The shared native reader previously cleared its response array while the parsed
JSON document still borrowed that array. Status/property lookup then failed before
any policy action. The regression reproduced this failure with the old code.
The correction parses into independently owned document storage, clears the source
buffer on every path, and retains caller disposal. Malformed and terminal replies
remain failures; dispatch and mutation retry rules are unchanged.

The corrected package passed the controlled Profile 3 shared-policy rest test on
**2026-09-25**. After manual launch and health initialization before native Continue,
`full-agent --agent-stop-at-map` completed **4 attempted / 4 accepted / 4 reconciled
actions in 27 reads**, with zero stale rejections and nothing pending. The result
was `truncated/external_stop` at an actionable map, with decision kinds `rest` and
`map`. Native UI confirmed HP **45/83 → 69/83**, deck **6 → 7**, and unchanged
399 gold. This demonstrates the healed rest/card-reward/map path through the same
public-only chooser as headless; it is not a full campaign acceptance.

Normal Save and Quit and game Quit completed, followed by stopped process/closed
listener checks, exact quarantine/purge of four owned files and verification of
all **429 unchanged base files with zero overlays**, by **11:02:21 UTC**.
The installation is now absent. The installation identity and exact result remain
in `validation.json`. The [native candidate boundary](../../../../docs/AGENT_CONTRACT.md#native-full-run-v2-candidate)
and remaining potion, hand-selector, treasure, pickup and recording gaps remain.

The preceding diagnostic manifest `7be74f7e…`, source `1989124`, stopped at the
saved rest site with `read_context_failed` (**0/0/0**, one read). Native Save and
Quit followed by normal Quit preserved the run. Process/listener shutdown,
four-file owned cleanup and 429 unchanged base files with zero overlays were
verified by **2026-09-25 10:09:24 UTC**. Its exact live record is in Git `53e2255`;
it is not repinned to this corrected package.

Current evidence and the preserved prior package/record are under
`/private/tmp/sts-bridge-qqc_ae6w`. Current install inputs are at
`/private/tmp/sts-unified-bridge-release`.
