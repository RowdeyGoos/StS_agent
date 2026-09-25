# Current unified release

This directory binds the current package to its source and validation.
[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns live
support; [bridge usage](../../README.md#interactive-rest) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, independent review, installation and current live status |

Manifest SHA-256:
`1926afc8917efd6b27165057d412bb63bd33a2bfed4ba6570773ca19083e54e5`.
It binds **423 inputs across 51 projects**, committed in `ff3cb5f`; the rest feature
is in `24f620d`. DLL: **1,470,464 bytes**, SHA-256
`b1a4252411a14ee32b5708bf01ea41e24cefb2d54aaa7f9ceb65963df90e4441`.

The final release gate passed **83 groups in 307.672 seconds**, including
reproducible build, public transport, native metadata/dependency verification,
packaging and disposable installation/cleanup. It includes **12,925 native
regression checks**, **625 rest checks**, **22 rest host tests**, **18 rest
Python/C# scenarios** and **1,546 router checks**. The focused reward mode passed
87 checks; those cases are also included in the full native regression.

`rest_v3` exposes individual option, select/deselect/confirm/cancel and reward
decisions on the existing room module. Smith/Cook cancellation requires unchanged
deck/inventory and restored rest controls. Heal retains its exact Dream Catcher
card/Tiny Mailbox potion reward continuation. Collection, native card Skip and
explicit dismissal remain distinct. Unopened cards stay hidden; stale owners,
changed menus, late responses and uncertain input cannot become clean completion.
Independent review is clear; measured review intervals and corrections are in
`validation.json`.

**Representative rest tests passed live on 2026-09-25.** After manual launch on
Profile 3 and native Continue, controlled relic grants and native map entry
established the rest sites. Smith and Cook both canceled before selection and
after selecting their previews, preserving the deck and restoring all options.
Heal collected Dream Catcher's card and Tiny Mailbox's two potions. A separate
Dream Catcher offer passed card Skip followed by explicit parent dismissal.

| Case | Attempted / accepted / reconciled | Reads |
| --- | --- | --- |
| Smith immediate cancellation | 2 / 2 / 2 | 4 |
| Smith preview cancellation | 3 / 3 / 3 | 13 |
| Cook immediate cancellation | 2 / 2 / 2 | 4 |
| Cook preview cancellation | 4 / 4 / 4 | 22 |
| Heal card + two potion rewards | 5 / 5 / 5 | 30 |
| Heal card Skip + parent dismissal | 4 / 4 / 4 | 29 |

The collected rewards increased the deck from five to six cards and the belt
from one to three potions. Skip preserved both counts. Both Heal cases returned
to native Proceed. By **07:11:34 UTC**, normal quit and owned cleanup passed:
game/listener stopped, four generated files removed, zero overlays, and all
**429 base files** unchanged. This does not complete the full shared native
interface or establish other rest/relic variants.

An initial gate caught a shared-fixture compilation mismatch; the next caught an
unintended regex dependency. Both were corrected and focused checks passed before
the final accepted gate. Neither failed candidate emitted an accepted manifest or
was installed. Their logs remain at the paths in `validation.json`.

Gate/operational evidence is retained at `/private/tmp/sts-bridge-cscqj2sh`; current
install inputs are at `/private/tmp/sts-unified-bridge-release`. The prior package
and exact records are retained under the gate's `previous-*` paths and in Git
`b6e406c`. That release passed one-card automatic removal with **2/2/2** parent
actions, no child selector and an actionable map, followed by complete owned
cleanup. Its result remains bound to manifest `308e9683…`, not this package.
