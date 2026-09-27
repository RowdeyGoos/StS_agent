# Current unified release

The full client now stops after four consecutive confirmed no-mutation stale
rejections. A validated accepted dispatch resets that streak; waiting, changed
tokens and reconciliation do not. Cumulative reporting, the legacy total cap,
uncertain-receipt stops and time/read/action limits remain unchanged.

[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns support;
[bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, review, package reuse and separately bound live evidence |

Manifest SHA-256: `325f2611735c00376775a0d6f4c2c4c1aa1657a93477e056cf777a318321bf20`. Source: `2e9e66d4403e50dfcc7242498af49b7026b0f0d2`.
The final gate passed **85 groups in 399.505 seconds**, including
**173 client tests**, **1,719 router checks** and **17,151 native event checks**.
The focused 23 tests and independent review also passed.

Only the client and its two regression files changed among 489 bound inputs.
The native DLL and all three package files are byte-for-byte identical to the
preceding accepted release: DLL **1,819,648 bytes**, SHA-256
`66ca1e3dcb4fa4de9b509e8e8dbce45e00c27efd3f20ae466c352443aaadf59a`. Existing install inputs passed exact
identity checks. Fresh installed/runtime, authenticated health and compatibility
checks passed before resuming in the same game process.

The [preceding live segment](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#symbiote-passed-and-settled-combat-stale-stop-2026-09-27) passed Symbiote at **4/4/4**
on a 105-card deck, then stopped at floor 99 with **116/112/112** controller counts
and nothing pending. That evidence retains manifest `c78ae051…` and its original
source, with the complete record preserved in Git `2e9e66d` and this gate's
`previous-release-record`.

The corrected client then finished the final combat, rewards and Architect,
returning `victory/none`: **12/12/12 new actions**, 262 reads, zero stale rejections
and nothing pending. Native Victory was also observed. This is an assisted saved
continuation, not a fresh uninterrupted campaign; separated-stale recovery remains
fixture-tested because the final segment had no stale rejections.

Normal quit, exact owned-file removal and base verification passed by
**2026-09-27 12:56:22 UTC**: zero overlays and all **429** base files unchanged.
