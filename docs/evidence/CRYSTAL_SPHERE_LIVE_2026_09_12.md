# Crystal Sphere live test — September 12, 2026

Scope: user-authorized testing on manually launched Profile 3, starting at untouched
Crystal Sphere initial choices with potion capacity. One combined production bridge;
no profile/save/history/Cloud filesystem access. No uncertain mutation was retried.
This record distinguishes partial gameplay success from verified final handoff.

## First observation

Release `e2f24a7cfc670cf1fb13f43b539b07fa4cea3b2503873cdeda90b07a47df488a`
stopped on its first GET with `invalid_response`. Zero gameplay actions were
attempted; a read-only follow-up found the listener closed. The initial cause
remains unproven. Separate inspection found missing sphere action grammar in the
shared Python client and C# HTTP parser. Exact child action support, canonical bounds
and real-socket POST regressions were added and independently reviewed.
Normal quit, exact owned quarantine/purge, 429 unchanged base files and zero overlays
passed before the corrected installation.

## Corrected transport: child complete, exit verification failed

Release `e77bfc9bc23ce05d0d60ccadcaf9a73985c4c3ea59a5189d394286138efa5546`
passed its initial read. Uncover Future was accepted; all four sphere child actions
were accepted and reconciled. The original event callback completed and native Leave
was accepted. The map visibly opened; displayed gold changed from 119 to 78, consistent
with the 51 entry payment and 10 earned gold.

The final parent action did not reconcile: parent attempted/accepted/reconciled
2/2/1; child 4/4/4; 274 event reads; `unsupported_state`; independent map check not
attempted. This is partial live evidence, not a successful event/map handoff.
The sanitized response log retained HTTP status and bounded native diagnostic
categories, not raw response bodies or credentials.

Static inspection of the pinned assembly shows the sphere's Proceed handler calls
`RunManager.ProceedFromTerminalRewardsScreen`, which opens/enables the map without
removing the completed sphere overlay. The fixture had incorrectly cleared it.
The correction retains native Proceed, then removes only that exact sole completed
overlay during parent-owned disposal through `NOverlayStack.Remove`. It requires
successful original/exit tasks, exact world ownership, unchanged inventory, an empty
stack and an actionable non-traveling map. A guard set before removal prevents
retry after any cleanup failure. 593 focused sphere checks and independent review
cover normal/free-node cleanup and foreign/extra overlays, no-op/throwing removal,
changed inventory, map closure, changed owner and new travel during removal.

Normal quit and exact owned quarantine/purge passed. The base check again found
429 unchanged files, hash `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`,
and zero overlays. The next release/test status is recorded in
[current status](../STATUS.md) and the
[current release validation](../../bridge/Sts2AgentBridge/releases/current/validation.json).

Exact result and sanitized diagnostic paths/hashes are retained in the current
validation record's per-attempt entries. The recorded source commit is a checkout
base; each release manifest binds exact uncommitted input bytes. First failure
elapsed 0.469 seconds; corrected-transport gate 199.876 seconds; focused transport
gate 29.505 seconds. Other implementation/review/user-wait times were not separately
measured.

## Final corrected release: passed

Release `7db195a80d67296c6930b135785724505fa26ea3c4475588bfc55fabeacecccf`
passed the complete prepared Uncover Future path. Parent actions reconciled 2/2;
sphere child actions reconciled 4/4; 18 event reads. The original callback and exact
completed-overlay removal finished, and the independent core map check passed on
its first read with one legal candidate. The map was visually confirmed, with 78
gold after the 119 start. No map node was selected.

This establishes the representative reveal/gold/exit path. Payment Plan, explicit
switching between both tools and card/potion/relic reward variants remain outside
this live result. Public parent effects remain `unverified`; this is not an
all-effects certificate or strategic-quality result.

Normal quit, stopped process/closed listener, exact owned quarantine/purge and
429 unchanged base files with zero overlays passed. No test bridge remains installed.
The final release gate passed 71 groups in 200.453 seconds, with 9,819 native checks,
593 focused sphere checks and independent semantic review. Final live duration
was not separately measured. Per-attempt results and diagnostic hashes remain in
[current validation](../../bridge/Sts2AgentBridge/releases/current/validation.json).
