# Combined bridge live batch

Status: generic single-upgrade and core map return passed on the second
installation. Combat orchestration stopped before chooser input; combat-choice
and reward/map completion remain unverified. Both live installations were cleaned up. The user authorized live testing after feature preparation and
confirmed manual readiness on Profile 3.

## First installation and event attempt

- Source: `72aaaf528200523e93479d7f5100f3482e191151`.
- Accepted release SHA-256:
  `74e3cfee962253f9bab0fbc8b13e1aa80df1e134d20c31e5bbc5cb029afc01a8`.
- DLL: 784896 bytes,
  `3424b5d15191f458faab369de20df151477372a2a129c41b0df78753aa327797`.
- Historical installed state:
  `4b8cea51c2d3e334c888db600a94cc7ff0b7fa972833f4ed22466f3df4d40a9f`.

Preparation verified the stopped game and closed port, the exact pinned 429-file
base and exactly two installed overlay files. Client ownership/configuration
preflight passed. After manual launch, the exact running process, authenticated
health, compatible build manifest and public main menu passed. UI showed Profile 3.

UI continued the existing test run to a treasure room. Controlled console setup
issued eight `card BASH Deck` commands and `event SAPPHIRE_SEED`; the console
reported successful additions and event entry. However, the subsequent UI still
showed a 12-card deck and an 11-card upgrade grid. This did **not** establish the
intended larger-deck/off-screen premise. The reason those additions did not appear
in the event deck was not determined.

The existing shared `BridgeClient` and generic host ran with a bounded custom
provider intended to select advertised slot 15 once, then confirm its exact
preview and verify core map readiness. The provider was never given an admitted
child. Consume was accepted and the UI showed HP 77 → 80 plus the upgrade grid.
The controller stopped with:

- `code: unsupported_state`, 258 reads;
- parent attempted/accepted/reconciled: **1 / 1 / 0**;
- card child attempts/accepted/reconciled: **0 / 0 / 0**;
- admitted child episodes and completed card/item children: **0**;
- latest effect label: `unverified`; map check not attempted.

No card-selection input, confirmation or upgrade was dispatched. There was no
retry or manual completion of the unresolved bridge operation. The exact native
admission diagnostic was not retained, so the observed result does not identify
which native readiness check blocked admission.

Normal application quit succeeded. Runtime checks found the game stopped and
listener closed (three process samples, two port samples). Quarantine state was
`36d7569bbf6e748769380b4e237d876a20fcfbf6ff2950df8e8c6a5742fb23e2`;
purge removed the four owned generated files and returned the campaign to absent.
Post-cleanup base verification passed: 429 files, zero overlays, projection
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
No profile/save/history/Cloud filesystem data was read. Credentials stayed within
the existing authenticated client's read lease and were cleared after use.

## Reproduced compatibility correction

Source inspection found that single-upgrade selection required the hitbox's exact
runtime type to be `NClickableControl`, whereas the multi-upgrade and transform
adapters accept derived controls and retain exact object identity. The single
fixture was changed to use the existing derived-hitbox fixture class. Before the
correction, native admission failed at `generic child FIRST_EVENT` in
`/private/tmp/sts-bridge-mxm6j4_e`.

The correction uses the same native validity predicate as the sibling adapters.
It preserves exact hitbox reference, holder/card/model/highlight/material identity,
visibility, enabled state, native clickability and all preview/effect checks.
A regression rejects replacement with another derived hitbox. The focused native
suite passed **3,897** checks in `/private/tmp/sts-bridge-cd7fegve`; one independent
semantic review found no blockers. This is a reproduced compatibility defect,
not proof of the first live failure's cause. Current release records own the final
combined gate and package identity.

The next live attempt should first retain the bounded native diagnostic if
admission fails, verify the actual advertised domain, and establish any off-screen
target premise from the visible selector. Combat choices, both reward policies
and event-to-core map return still belong to the pending batch. Phase elapsed
times for live setup and review were not captured.

## Corrected release prepared

The final combined gate passed 71 check groups in **148.735 seconds** at
`/private/tmp/sts-bridge-70buv13o`, including production reproducibility, actual
native-to-host integration and owned package/install/cleanup fixtures. Source
commit is `a57cb98`; accepted release SHA-256 is
`731a8cf1c51ecdb5cfa4ef574085122c70606c62eea4a896312fb05506f6c755`.
The preceding package and release records were preserved under
`/private/tmp/sts-bridge-retained-release-km0yyy77` before publishing the correction.

The game was rechecked stopped with its listener closed. Corrected installation
passed with a fresh owned state:
`050f6a250dd2f4241bff666922dee80ce77ff2f97fdb0d7687177c25b67e626b`.
Post-install verification found 429 unchanged base files plus exactly two overlay
files. Client release/ownership/configuration preflight passed without reading
credential contents. This installation remains active on disk, awaiting manual
relaunch; cleanup is pending. No corrected-binary live result exists yet.

## Second live attempt: generic upgrade and core map passed

Manual readiness, exact running process, authenticated health, compatible manifest
and public main menu passed for release
`731a8cf1c51ecdb5cfa4ef574085122c70606c62eea4a896312fb05506f6c755`,
installed state `050f6a250dd2f4241bff666922dee80ce77ff2f97fdb0d7687177c25b67e626b`.
UI confirmed Profile 3 and continued its existing test run. Console setup issued
only `event SAPPHIRE_SEED`, with success visibly verified before bridge control.

The actual shared client/generic host selected the first advertised card,
confirmed its exact upgrade preview, completed the card effect and chose Proceed.
The original response parser still validated each response; a test wrapper
retained only its bounded native diagnostic code after validation. Diagnostics
were `parent_ready`, `child_ready`, `parent_ready`, `map_ready`.

- Parent attempted/accepted/reconciled: **2 / 2 / 2**.
- Card child attempted/accepted/reconciled: **2 / 2 / 2**.
- One admitted and completed card child, no completed item children.
- Four total actions, 14 event reads; resolved with no error.
- A fresh core map decision passed after one read, with one actionable candidate.
- Combined event and map elapsed time: **1.506 seconds**.

The latest parent effect label remained `unverified` after Proceed, as specified;
one completed card child retains the verified upgrade. UI showed the map. This
establishes ordinary single-upgrade and event-to-core map return, not off-screen
upgrade behavior, all event branches or a full run. The result summary is retained
at `/private/tmp/sts-upgrade-retest-result.json`.

## Second live attempt: combat transition stopped

A fresh core map read advertised `select:0` for monster column 4, row 7. Its one
accepted action was reconciled by a complete map observation for the same
destination; UI showed combat at 80/80 HP. The shared `combat-map` controller ran
with `first-select` chooser and `first-card` reward policies.

It stopped at stage `combat` with `unexpected_combat_round`:

- Combat attempted/accepted/reconciled: **9 / 7 / 6**.
- Two confirmed no-mutation stale rejections, 30 combat reads, 19 chooser probes.
- No admitted/completed chooser summaries; rewards and map check not attempted.
- UI showed Neow's Fury's discard selector in turn 2, allowing up to two cards.
  No selector input was sent. Enemy HP was visibly 16/40; player HP remained 80/80.
- A single read-only diagnostic combat observation returned `waiting`.

The pending combat action was not retried or manually completed. No exact pending
versus observed round pair was retained, so the live result alone does not prove
which round transition triggered the check. The predecessor's tested
`apply_combat_live._poll_after_action` waits through changed original-round
observations after end-turn; the newer host immediately rejected them. Focused
regressions reproduced that missing wait before the correction.

Normal quit, stopped process and closed port passed (three process/two port
samples). Quarantine state was
`9160526d7ee99de0e5544812b80dbdb78a0a411f4d4d44f6911ced5b66fb9eff`.
Purge removed the four generated files. Post-cleanup verification found the same
429-file pinned base and zero overlays.

## Combat host correction

Only an accepted pending `end_turn` in its original round enters the existing
bounded wait/chooser path. It retains the reservation and counts; no combat
redispatch or early reconciliation is allowed. Exact next round or terminal
combat still reconciles; backward/skipped rounds and a card action advancing the
round still fail. All deadlines and read/action bounds remain.

Nine focused combat-host tests pass, including optional zero and multiple chooser
selections during this wait, unchanged round timing out without redispatch, and
invalid round changes. The two new waiting scenarios failed before the correction.
The focused host gate passed all ten groups in **9.776 seconds**, including the
existing shared-client socket integration (`/private/tmp/sts-bridge-qy139kvm`).
One independent semantic review found no blockers. Current release records own
the final combined gate and package identity. No native bridge change is needed.

## Combat host retest prepared

Source `370bd77` passed the final 71-group release gate in **146.105 seconds**
(`/private/tmp/sts-bridge-tx2i28t8`). Accepted manifest SHA-256:
`fcf7e2999df081cfdd07e8364c48c5646c6dc34fa7198bf911be816d489a1bdb`.
Its native DLL and canonical package exactly match the preceding accepted
release. The already published, validated package was reused; the changed host
is covered by the new source inventory and executed checks.

Stopped-game/closed-listener checks passed before installing with fresh state
`3599640917195929280b307348fd83cd7a7d3e9d9602821d11a25be45feb6b00`.
Post-install verification found the pinned 429 base files plus exactly two
overlay files. Release and client ownership/configuration preflight passed
without reading credential contents. This third installation is awaiting manual
relaunch and still requires cleanup. The corrected combat wait has not yet been
live-tested; the same native binary's generic upgrade/map result remains valid.
