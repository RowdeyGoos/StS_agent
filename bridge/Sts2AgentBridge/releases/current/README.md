# Current unified release

This directory binds the current package to its source and validation.
[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns live
support; [bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, independent review, installation and live status |

Manifest SHA-256: `7be74f7e95ad55e39e3b333eacc17547d7b888edf7cfef13d6ac1a3821bde5ce`.
It binds **439 inputs across 51 projects**, source `1989124`, feature `49a6de1`.
DLL: **1,567,232 bytes**, SHA-256
`b5eda18a8bc8f7ff8e556ce43ccbfb594b3bd934ced70a15a1fd578253515307`.

The final release gate passed **83 groups in 311.142 seconds**, including
reproducible builds, native metadata/dependency checks, packaging and disposable
installation/cleanup. It includes **164 client tests**, **1,624 router checks**,
**13,372 native regression checks**, **656 rest checks**, and the actual-listener
full-graph/2,048-slot/nested-receipt test. These are offline checks. The focused
host checks passed 14 tests in 0.67 seconds; independent semantic review passed
in 46 seconds. The earlier 8,177-test Python result remains historical evidence
for source `a39c40f`; this correction reran affected checks and the release gate.

This correction retains closed observation failure categories and validated
action counts. It reports which read boundary failed without exposing exception
messages or native data. Failure still stops the host without a mutation retry.
The diagnostic test identified `read_context_failed` before any action. Source
inspection and a failing regression identified a borrowed JSON buffer being
cleared before its fields were read. This package itself remains uncorrected.
The [native candidate boundary](../../../../docs/AGENT_CONTRACT.md#native-full-run-v2-candidate)
and remaining potion, hand-selector, treasure, pickup and recording gaps remain.

The diagnostic Profile 3 test stopped on its first read (**0/0/0**, one read).
Native Continue reached the same saved rest site. Save and Quit followed by
normal Quit preserved the run. Process/listener shutdown, four-file owned cleanup
and all **429 unchanged base files with zero overlays** were verified by
**2026-09-25 10:09:24 UTC**. This package is no longer installed.

The previous manifest `3e5a097e…`, source `a39c40f`, stopped on its first shared
read at the saved rest site, before any policy action (**0/0/0**, one read).
The host retained only `native_failure`, losing the underlying category. Native
Save and Quit followed by Quit preserved the run. Process/listener shutdown,
four-file owned cleanup and all 429 unchanged base files with zero overlays were
verified by **2026-09-25 09:43:22 UTC**. The exact record is in Git `39e2267`.
Earlier rest acceptance remains with its original package in Git `4f8b633`;
neither result establishes this diagnostic candidate's live acceptance.

Current evidence and the preserved prior package/record are under
`/private/tmp/sts-bridge-18v38y_r`. Current install inputs are at
`/private/tmp/sts-unified-bridge-release`.
