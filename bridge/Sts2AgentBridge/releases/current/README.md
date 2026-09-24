# Current unified release

This directory binds the current candidate to its source, tests and package.
[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns live
support; [bridge usage](../../README.md) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release validation, independent review and current live status |

Manifest SHA-256:
`308e9683a74a3d60ef2071e3dd6f97583e2ace1adb2494778a9aaee73e89105e`.
It binds **416 inputs across 51 projects**, committed in `b7ee84b`.
DLL: **1,443,328 bytes**, SHA-256
`704695815a5e9086a188a6d60db929fad160950554da5cdc9770d220849cd9fc`.

The release gate passed **83 groups in 304.387 seconds**, including reproducible
build, shared socket requests, package verification and disposable owned
installation/cleanup. The full native regression passed **12,799 checks**;
focused automatic-removal validation passed **320 checks**. Independent semantic
review completed at 20:39:05 UTC (134 seconds) with no blockers; its two suggested
negative cases were added and passed. Earlier reviews retain their original scope.

The correction verifies automatic completion of an exact outer removal request
without requiring a separately observed call to its generic implementation. For
that path, the null-filter removable domain is captured at entry, must fit within
the native automatic bound, and must exactly match the returned originals. Both
owned tasks and the exact deck change still have to complete. Arbitrary supplied
filters are never invoked. The prior live failure's exact predicate remains
unproven. The new release separately passed the one-card Dark Door live case.

**Live automatic removal passed on 2026-09-24:** one eligible Bash was removed,
**2/2/2 parent actions** reconciled, no child selection was invented, and the
actionable map exposed two legal destinations. Owned cleanup completed by
**20:58:54 UTC**: game/listener stopped, four generated files removed, zero overlays
and all 429 base files unchanged. Exact installation and cleanup identities are
retained in `validation.json`. This is one representative automatic-removal case.

The preceding `00280cad…` release passed the original ten-entry Fake Merchant
rewards after native Continue: **12/12/12** actions, all entries collected,
including Fake Mango, then the actionable map. Its subsequent one-Bash Dark Door
attempt stopped at **1/1/0** with `pending_selectorless_request`, despite native
removal and visible Proceed. No uncertain action was retried. Exact cleanup
completed by **20:31:55 UTC**: four generated files removed, zero overlays,
process/listener stopped and all 429 base files unchanged. These live results
remain bound to that original package in `prior_reward_removal_attempt`.

Gate and operational evidence are retained at `/private/tmp/sts-bridge-hzudn88q`;
install inputs are at `/private/tmp/sts-unified-bridge-release`. The gate's
`previous-*.json` files retain the preceding candidate. Git `dbd7861` and the
[M7 record](../../../../docs/evidence/AGENT_CAMPAIGN_M7_2026_09_24.md) retain the
accepted assisted campaign under its original package identity. These corrections
do not complete the full shared native interface.
