# Current unified release

This release fixes shared deck selectors that waited indefinitely when a large
deck had fewer allocated native controls than eligible cards. The full candidate
domain stays available; only an explicit selection navigates toward an original.
The driver validates the retained control pool and selected set, finishes native
allocation after slow frames, and stops scrolling before exact one-shot input.
Shared shop, rest and compound pickups use this driver. The separate generic-event
selector adapters keep their existing bounds.

[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns support;
[bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, review, installation and separately bound live evidence |

Manifest SHA-256: `fed09e937f44d54c52064b0a9c0adc09a03bcfd7ca21bbd3a805277b4151da37`.
It binds **485 inputs across 52 projects**, source and feature `327e7da`.
DLL: **1,800,704 bytes**, SHA-256
`e90607c18b127d3299f67b5ab1ba7b0039f35ab237d33338a56c7762cc7a3bbd`.

The final gate passed **85 groups in 369.018 seconds**, including reproducible
builds, native metadata/dependency checks, packaging and disposable cleanup.
It includes **168 client tests**, **1,639 router checks**, **229 event wire cases**,
**16,972 native event checks**, **656 rest checks**, **21 shop core checks**,
**252 campaign checks** and **179 potion checks**. Focused virtualized-deck
regressions passed **946 checks in 4.260 seconds**. Independent source review
found the slow-frame allocation edge, then cleared its correction (**429 seconds**
across three reviews). All 102 bound Python files match the preceding release;
prior broad Python delivery evidence remains separate and unchanged.

The preceding [shared-v2 route](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#shared-v2-neow-recovery-and-large-deck-cook-stop-2026-09-26)
recovered Neow's Small Capsule reward and map return, then completed four fights
and Slippery Bridge. Cook's 33-card selector waited with **51 attempted / 51
accepted / 50 reconciled** and pending work. No manual gameplay intervention or
mutation retry followed attachment. Normal Quit and exact cleanup passed by
**17:39:16 UTC**, leaving zero overlays and all 429 base files unchanged. Neither
this nor the earlier 2/1/0 uncertain reward attempt is reconciled by cleanup.

The corrected package was installed and verified by **18:11:04 UTC** on
2026-09-26, with two exact overlay files and all 429 base files unchanged.
Installed state:
`279151f568527c80cdd9f860dee982da7fa90000761f9858c34ce06c576602ca`.
It awaits a manual Profile 3 launch to continue the saved campaign for a focused
Cook selection/preview/removal retest, then the remaining shared-v2 act/ending
route. No live recovery or completed campaign is claimed for this artifact.
The disposable retest and continuation helpers passed eleven offline cases.

The preceding release's exact record remains in Git `327e7da` and
`/private/tmp/sts-bridge-0ceoerz0/previous-release-record`; its package inputs are
under `previous-install-inputs` alongside it. Prior successful and failed live
cases retain their original manifest/source identities in the dated ledger.
