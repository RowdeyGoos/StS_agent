# Current unified release

This directory binds the current package to its source and validation.
[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns live
support; [bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, independent review, installation and live status |

Manifest SHA-256: `3e5a097e4ace0ba01ffb63f2cea67854bfc5c1d322a76ac7c043421443a09064`.
It binds **439 inputs across 51 projects**, source `a39c40f`, feature `49a6de1`.
DLL: **1,565,184 bytes**, SHA-256
`d322c0b824d35ca551e8de8a6b30ef1a61d12e051f3baf2655ee1c01889f69fb`.

The final release gate passed **83 groups in 313.512 seconds**, including
reproducible builds, native metadata/dependency checks, packaging and disposable
installation/cleanup. It includes **13,372 native regression checks**, **656 rest
checks**, **1,600 unified router checks**, 18 rest Python/C# scenarios, and the
actual-listener full-graph/2,048-slot/nested-receipt test. These are offline checks.
The complete Python suite passed **8,177 tests in 1,826.64 seconds**, with two
Gymnasium warnings about fixed observation fields; compilation also passed.
Independent semantic review is clear within the [candidate boundary](../../../../docs/AGENT_CONTRACT.md#native-full-run-v2-candidate).
Measured review intervals and gate timings are retained in `validation.json`.

The package adds opt-in `agent_v2` public graphs and semantic dispatch through the
existing native owners and shared Python policy. It exposes supported rest/shop
and event children separately, preserves exact receipt lineage, withholds hidden
information and stops on uncertainty. General potion/hand-selector coverage,
treasure claiming, removal cancellation, reward rerolls and public live recording
remain open. **This is not complete native coverage or live v2 acceptance.**

The package is installed for the next controlled Profile 3 test, awaiting manual
launch. Installation and exact overlay verification passed: the expected two
package files are present and all **429 base files** remain unchanged. Owned state
SHA-256: `b739d04f39fee68974a03a806b79c74550ea545c50acaa55588e3971af74a298`.
No game action has been sent with this release. Cleanup follows the live test.

The previous rest package and evidence remain bound to manifest `1926afc8…`, source
`ff3cb5f`, and Git record `4f8b633`. Its Smith/Cook immediate/preview cancellation,
Heal card/two-potion collection and card Skip/dismissal passed **20/20/20 actions**
across 102 reads, followed by normal quit and complete owned cleanup at
**2026-09-25 07:11:34 UTC**. Those results do not establish this candidate's v2
projection or shared-policy behavior.

Evidence and the preserved prior package/record are under
`/private/tmp/sts-bridge-rul6heyh`. Current install inputs are at
`/private/tmp/sts-unified-bridge-release`. One initial release attempt stopped on a
fixture compilation error; the corrected focused check passed before the final
gate. The failed attempt emitted no accepted release manifest and was not installed.
