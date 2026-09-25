# Current unified release

This release connects full event rewards to the production response validator.
[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns live
support; [bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, review, installation and separately bound live evidence |

Manifest SHA-256: `2d9a256032206ea0117c6caef38fad54a7180a2b635f7821d2982660fcff9c23`.
It binds **464 inputs across 52 projects**, source `b55c51d`.
DLL: **1,684,480 bytes**, SHA-256
`042cf453dbedbb55eff8ca8f7b0725217212ae1cf73e9e846a7c6e8fadb2d809`.

The final gate passed **85 groups in 313.361 seconds**, including reproducible
builds, native metadata/dependency checks, packaging and disposable cleanup.
It includes **168 client tests**, **1,639 router checks**,
**211 event wire cases**, **13,986 native event checks**,
**656 rest checks**, **252 campaign checks** and
**179 potion checks**. Independent semantic review found no blocker.
Earlier broad Python results and their focused corrections remain separately
bound; no new broad run is claimed.

The production classifier now recognizes the existing `full_rewards_v1` descriptor,
reads and receipts. It validates exact keys, versions, nonce, bounded history and
phase-specific actions without exposing unopened cards. Waiting and resolved
children retain the parent event owner; failed receipts still stop. The regression
failed before the fix and now passes actual wire bytes through this boundary.
The fixtures do not establish live gameplay acceptance.

The preceding manifest `bc0767b1…`, source `d9eda0d`, passed Neow projection and
accepted Lost Coffer. Native Loot displayed Flex Potion and Add a card, then
`read_native_failed` stopped at **1 attempted / 1 accepted / 0 reconciled**,
35 reads and a pending parent action. No reward action ran or uncertain mutation
was retried. Cleanup finished by **16:26:04 UTC** with four generated files removed,
zero overlays and all 429 base files unchanged. Original evidence remains in Git
`ca440d3`, the [live ledger](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md)
and this release's `previous-release-record` directory.

The saved-campaign Lost Coffer retest passed: **6 attempted / 6 accepted /
6 reconciled**, 42 reads, no stale rejection or pending action. Potion replacement,
card choice and event/map return completed; HP/gold remained 88/88 and 466, with
the deck growing seven to eight. A subsequent debug shop switch timed out with
900 reads and no new agent action because the existing full session still tracked
the map. It does not establish shop acceptance.

Normal quit and exact cleanup finished by **16:58:22 UTC**: four generated files
removed, zero overlays and all 429 base files unchanged. The game is stopped and
the owned bridge installation is absent. No profile/save/history/Cloud filesystem
content or live trajectory corpus was accessed.

The [native candidate boundary](../../../../docs/AGENT_CONTRACT.md#native-full-run-v2-candidate)
remains explicit. Neow's Bones needs a compound relic-pickup/curse continuation.
Shared event rewards, shop extensions, empty chests, arbitrary nested pickups and
a full v2 ending retain their documented live-evidence limits.

Current evidence and the preceding release record are under
`/private/tmp/sts-bridge-og6_b103`. Prior install inputs are retained in its
`previous-install-inputs` directory; current install inputs use
`/private/tmp/sts-unified-bridge-release`.
